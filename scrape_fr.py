import requests
from bs4 import BeautifulSoup
import pprint
import sqlite3
import os
import json 
from feedgen.feed import FeedGenerator
import pickle
import time

rss_host = "https://getwishlisted.xyz/"
rss_self = rss_host + "ccs_fr.xml"
rss_dir = "/var/www/html/ccs_fr.xml"
#rss_dir = "ccs_fr.xml"
rss_obj = "feed.obj"
json_dump = "/var/www/html/proposals.json"
getmonero_url = "https://ccs.getmonero.org"
#irc message
webhook_endpoint="http://theurl dot com /message"
webhook_password="hunter2"

def send_msgs(msg_list):
    global webhook_password, webhook_endpoint
    headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}

    for msg in msg_list:
        data = {
            'message': msg[0],
            'password': webhook_password
        }
        r = requests.post(webhook_endpoint, data=json.dumps(data), headers=headers)
        if r.status_code == 200:
            announce_success(msg[1])
            if "funded" in msg[0]:
                announce_funded(msg[1])

        time.sleep(1)

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
                                        notify integer,
                                        announced integer
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
def announce_funded(address):
    print("at anounce funded")
    con = sqlite3.connect('ccs_addresses.db')
    cur = con.cursor()
    sql = """UPDATE proposals SET notify = 1 WHERE address = ?"""
    cur.execute(sql, (address,))
    con.commit()
    con.close()

def announce_success(address):
    print(address)
    print("at announce success")
    con = sqlite3.connect('ccs_addresses.db')
    cur = con.cursor()
    sql = """UPDATE proposals SET announced = 1 WHERE address = ?"""
    cur.execute(sql, (address,))
    con.commit()
    con.close()
    print(f"we successfully announced {address}")


def new_address(address):
    con = sqlite3.connect('ccs_addresses.db')
    cur = con.cursor()
    cur.execute('SELECT * FROM proposals WHERE address=?',(address,))
    rows = cur.fetchall()
    rows = len(rows)
    if rows == 0:
        print(f"adding too seen: {address}")
        sqlite_insert_with_param = """INSERT INTO proposals 
                          (address, notify, announced)
                          VALUES (?, ?, ?);"""
        cur.execute(sqlite_insert_with_param, (address,0,0))
        con.commit()
        con.close()
        return True;
    con.commit()
    con.close()



def main():
    create_db_tables()
    resp = requests.get("https://ccs.getmonero.org/funding-required/")
    #print(resp.content)
    soup = BeautifulSoup(resp.content, 'html.parser')

    soup = soup.find('section', class_='fund-required')
    ideas = soup.children
    msg_list = []
    rss_list = []
    rss_info = []
    ideas_data = []

    # first come, first serve

    for idea in ideas:
        try:
            for item in idea.find_all('a'):
                title = item.find('h3').text
                #print(title)
                link = item['href']
                goal = item.find("span", class_="progress-number-goal").text
                raised = item.find("span", class_="progress-number-funded").text
                contributors = item.find("p", class_="date-list contributor").text.split()[0]
                author = item.find("p", class_="author-list").text
                #print(link)
                resp2 = requests.get(f"https://ccs.getmonero.org{link}")
                soup2 = BeautifulSoup(resp2.content, 'html.parser')
                address = soup2.find('p', class_='string').text
                link = getmonero_url + link
                #[msg + address]
                proposal_info = []
                if new_address(address):
                    print("new add fin")
                    msg = f"NEW: {title}"
                    print("do we get here")
                    rss_info.append(msg)
                    rss_info.append(link)
                    rss_list.insert(len(rss_list),rss_info)
                    print("rss list?")
                    #send_msg(f"{title} has moved to funding! {link}")
                    proposal_info.append(f"{title} has moved to funding! {link}")
                    proposal_info.append(address)
                    print("time to err")
                    msg_list.insert(len(msg_list),proposal_info)
                    print("Yep")
                    #time.sleep(20)
                else:
                    print("not new")
                    #HAVE WE ANNOUNCED IT MOVED TO FUNDING YET?
                    con = sqlite3.connect('ccs_addresses.db')
                    cur = con.cursor()
                    sql = """SELECT * FROM proposals 
                            WHERE address = ?"""
                    cur.execute(sql,(address,))
                    rows = cur.fetchall()
                    #annoucned
                    if rows[0][2] == 0:
                        print("not new and not announced yet")
                        proposal_info.append(f"{title} has moved to funding! {link}")
                        proposal_info.append(address)
                        msg_list.insert(len(msg_list),proposal_info)

                    if float(goal) <= float(raised):
                        print("Wut")
                        pprint.pprint(rows[0][1])
                        print("wut")
                        if rows[0][1] == 0:
                            msg = f"FUNDED: {title}"
                            rss_info.append(msg)
                            rss_info.append(link)
                            rss_list.insert(len(rss_list),rss_info)
                            #send_msg(f"{title} is now fully funded! {link}")
                            proposal_info.append(f"{title} is now fully funded! {link} @luigi1111")
                            proposal_info.append(address)
                            msg_list.insert(len(msg_list),proposal_info)
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
    if msg_list:
        send_msgs(msg_list)
    if rss_list:
        for msg in rss_list:
    	    add_to_rfeed(msg[0],msg[1])


main()
