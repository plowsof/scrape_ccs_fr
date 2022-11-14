import requests
from bs4 import BeautifulSoup
import pprint
import sqlite3
import os
import json 
from feedgen.feed import FeedGenerator
import pickle
import socket
import time

rss_host = "https://getwishlisted.xyz/"
rss_self = rss_host + "ccs_fr.xml"
rss_dir = "/var/www/html/ccs_fr.xml"
#rss_dir = "ccs_fr.xml"
rss_obj = "feed.obj"
json_dump = "/var/www/html/proposals.json"
getmonero_url = "https://ccs.getmonero.org"
#irc message
irc_chanlist = [b"#monero-community"]
botnick = b"n1oc"
botpass = b""

def send_msg(msg):
    global botnick, botpass, irc_chanlist
    server = "irc.libera.chat"
    #server = "irc.freenode.net"
    #this function will hang while waiting for someone to say hello
    msg = bytes(msg, 'ascii')
    irc = socket.socket(socket.AF_INET, socket.SOCK_STREAM) #defines the socket
    print("connecting to:"+server)
    irc.connect((server, 6667))                                                         #connects to the server
    irc.send(b"USER "+ botnick + b" "+ botnick + b" "+ botnick + b" :hello\n") #user authentication
    irc.send(b"NICK "+ botnick +b"\n")                            #sets nick
    time.sleep(3)
    irc.send(b"PRIVMSG NICKSERV :IDENTIFY " + botnick + b" " + botpass + b"\n")
    time.sleep(3)
    ddos = 0
    for channel in irc_chanlist:
        ddos = 0
        irc.send(b"JOIN "+ channel +b"\n")  
        while 1:
            ddos += 1
            if ddos > 10000:
                break
            text=irc.recv(2040) 
            print(text)
            if text.find(b'PING') != -1:                          #check if 'PING' is found
                irc.send(b'PONG ' + text.split()[1] + b'\r\n') #returnes 'PONG' back to the server (prevents pinging out!)
            if b"End of /NAMES list" in text:
                irc.send(b"PRIVMSG " + channel + b" :" + msg + b"\n")
                #print(b"PRIVMSG " + channel + b" :" + msg + b"\n")
                #print("send msg")
                break

def create_fresh_feed():
    global rss_self, rss_dir, rss_obj
    fg = FeedGenerator()
    fg.title("Monero CCS Alerts")
    fg.description("Get alerted when an idea is moved to 'funding required' or becomes fully funded.")
    fg.link( href="https://ccs.getmonero.org/funding-required/")
    fg.link( href=rss_self, rel='self' )
    fg.language('en')
    #rssfeed  = fg.rss_str(pretty=True) # Get the RSS feed as string
    fg.rss_file(rss_dir) # Write the RSS feed to a file
    #so we can load / append later
    with open(rss_obj, 'wb+') as f:
        pickle.dump(fg, f)

def add_to_rfeed(title,url):
    global rss_obj, rss_dir
    if not os.path.isfile(rss_dir):
        create_fresh_feed()
    with open(rss_obj, 'rb') as f:
        fg = pickle.load(f)
    fe = fg.add_entry()
    fe.title(title)
    fe.link(href=url)
    #update the feed
    fg.rss_file(rss_dir)
    #pickle it for later
    with open(rss_obj, 'wb+') as f:
        pickle.dump(fg, f)

def create_db_tables():
    connection_obj = sqlite3.connect('ccs_addresses.db')
    cursor_obj = connection_obj.cursor()
    sql_create_projects_table = """ CREATE TABLE IF NOT EXISTS proposals (
                                        address text PRIMARY KEY,
                                        notify integer
                                    ); """
    cursor_obj.execute(sql_create_projects_table)
    connection_obj.close()
    '''
    connection_obj = sqlite3.connect('ccs_proposals.db')
    cursor_obj = connection_obj.cursor()
    sql_create_projects_table = """ CREATE TABLE IF NOT EXISTS proposals (
                                        address text PRIMARY KEY,
                                        url text,
                                        title text,
                                        goal real,
                                        raised real,
                                        notify text
                                    ); """
    cursor_obj.execute(sql_create_projects_table)
    sql_create_projects_table = """ CREATE TABLE IF NOT EXISTS donations (
                                    address text,
                                    amount real,
                                    height integer,
                                    txid text
                                ); """
 
    cursor_obj.execute(sql_create_projects_table)

 
    # Close the connection
    connection_obj.close()
    '''

def new_address(address):
    con = sqlite3.connect('ccs_addresses.db')
    cur = con.cursor()
    cur.execute('SELECT * FROM proposals WHERE address=?',(address,))
    rows = cur.fetchall()
    rows = len(rows)
    if rows == 0:
        print("A new address")
        sqlite_insert_with_param = """INSERT INTO proposals 
                          (address, notify)
                          VALUES (?, ?);"""
        cur.execute(sqlite_insert_with_param, (address,0))
        con.commit()
        con.close()

        return True

    print("seen before")
    con.commit()
    con.close()


def main():
    create_db_tables()
    resp = requests.get("https://ccs.getmonero.org/funding-required/")

    soup = BeautifulSoup(resp.content, 'html.parser')

    soup = soup.find('section', class_='fund-required')
    ideas = soup.children

    ideas_data = []

    # first come, first serve

    for idea in ideas:
        try:
            for item in idea.find_all('a'):
                title = item.find('h3').text
                link = item['href']
                goal = item.find("span", class_="progress-number-goal").text
                raised = item.find("span", class_="progress-number-funded").text
                contributors = item.find("p", class_="date-list contributor").text.split()[0]
                author = item.find("p", class_="author-list").text
                resp2 = requests.get(f"https://ccs.getmonero.org{link}")
                soup2 = BeautifulSoup(resp2.content, 'html.parser')
                address = soup2.find('p', class_='string').text
                link = getmonero_url + link
                if new_address(address):
                    msg = f"NEW: {title}"
                    add_to_rfeed(msg,link)
                    send_msg(f"{title} has moved to funding! {link}")
                else:
                    if float(goal) < float(raised):
                        con = sqlite3.connect('ccs_addresses.db')
                        cur = con.cursor()
                        sql = """SELECT * FROM proposals 
                                WHERE address = ?"""
                        cur.execute(sql,(address,))
                        rows = cur.fetchall()
                        if rows[0][1] == 0:
                            sql = """UPDATE proposals SET notify = 1 WHERE address = ?"""
                            print(sql)
                            cur.execute(sql, (address,))
                            msg = f"FUNDED: {title}"
                            add_to_rfeed(msg,link)
                            send_msg(f"{title} is now fully funded! {link}")
                        con.commit()
                        con.close()
                    else:
                        pass
                        print(f"not funded: {title}") 
                data = { 
                "title": title, 
                "raised": raised,
                "href": link,
                "address": address,
                "goal": goal,
                "contributors": contributors,
                "author": author}
                ideas_data.append(data)

        except Exception as e:
            print(e)
            pass

    with open(json_dump, "w+") as f:
        json.dump(ideas_data, f, indent=4, sort_keys=True)

main()
