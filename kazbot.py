import socket, sqlite3, string, os
from connection_settings import HOST, PORT, CHAN, NICK

class Kazbot(object):
   
    def __init__(self):
        self.debug = True
        self.IRC = socket.socket()
        
    # IRC Protocol Functions

    def connect(self):
        self.IRC.connect((HOST, PORT))
        if self.debug: print("Connected to: " + str(self.IRC.getpeername()))

    def send_data(self, data):
        self.IRC.send("%s\r\n" % data)
        if self.debug: print("I> " + data)

    def login(self):
        self.send_data("Nick %s" % NICK)
        self.send_data("User %s 0 * :%s" % (NICK, NICK))

    def join_channel(self):
        self.send_data("Join %s" % CHAN)

    def msg_chan(self, msg):
        self.send_data("PRIVMSG %s :%s" % (CHAN, msg))

    def msg_user(self, user, msg):
        self.send_data("PRIVMSG %s :%s" % (user, msg))

    def pingpong(self, buff):
        buff = buff.split()
        if len(buff) > 1: self.send_data('PONG ' + buff[1])

    # Database functions
    
    def initialize_database(self):
        if not os.path.isfile('factoids.db'):
            # Database does not exist - must create tables
            self.database = sqlite3.connect('factoids.db')
            self.dbcursor = self.database.cursor()
            self.dbcursor.execute('''CREATE TABLE registered_users
                                     (name varchar(16))''')
            self.dbcursor.execute('''CREATE TABLE factoids
                                     (name varchar(16), key varchar(30), 
                                      factoid varchar(300))''')
            self.database.commit()
        else:
            self.database = sqlite3.connect('factoids.db')
            self.dbcursor = self.database.cursor()


    # User Command Functions

    def register_user(self, msg):
        name = msg[0]

        if self.is_registered(name):
            self.msg_chan("You've already registered %s!" % msg[0])
        elif msg[2] != '3':
            self.msg_chan("You must be registered with NickServ to register with kazbot %s!" % name)
        else:
            self.dbcursor.execute("insert into registered_users values(?)", (name,))
            self.database.commit()
            self.msg_chan("%s succesfuly registered!" % msg[0])

    def add_factoid(self, name, msg):
        key = msg[0]
        data = string.join(msg[1:])

        if not self.is_registered(name):
            self.msg_chan("You havn't registered yet %s! Type: kazbot register" % name)
            return
        elif len(key) > 30: 
            self.msg_chan("Error: key must be less than 30 chars")
            return
        elif len(data) > 300: 
            self.msg_chan("Error: data must be less than 300 chars")
            return

        self.dbcursor.execute("select key from factoids where name=?", (name,))
        key_list = self.dbcursor.fetchall()

        self.dbcursor.execute("select * from factoids where name=? and key=?", (name, key))
        match = self.dbcursor.fetchall()

        if len(key_list) >= 100:
            self.msg_chan("Error: %s has reached their factoid limit of 100 factoids. Damn." % name)
        else:
            if match:
                self.dbcursor.execute("delete from factoids where name=? and key=?", (name, key))
                self.database.commit()
            factoid = (name, key, data)
            self.dbcursor.execute("insert into factoids values (?,?,?)", factoid)
            self.database.commit()
            self.msg_chan("Factoid succesfully entered")

    def get_factoid(self, name, key):
        self.dbcursor.execute("select * from factoids where name=?", (name,))
        factoid_list = self.dbcursor.fetchall()
        
        self.dbcursor.execute("select factoid from factoids where name=? and key=?", (name, key))
        factoid = self.dbcursor.fetchall()

        if not self.is_registered(name): 
            self.msg_chan("You need to register and add your own factoids %s! Try: kazbot help" % name)

        elif not factoid_list: 
            self.msg_chan("You don't have any factoids yet, %s. Try: kazbot add-factoid <key> <factoid>" % name)

        elif not factoid:
            self.msg_chan("You don't have a factoid with that key %s." % name)
        
        else: self.msg_chan(factoid[0][0])
        
    def list_keys(self,name):
        self.dbcursor.execute("select key from factoids where name=?", (name,))

        keys = []
        for i in self.dbcursor.fetchall():
            keys.append(str(i[0]))

        if not self.is_registered(name):
            self.msg_chan("You need to register and add your own factoids %s! Try: kazbot help" % name)
        elif not keys:
            self.msg_chan("You don't have any factoids yet, %s. Try: kazbot add-factoid <key> <factoid>" % name)
        else:
            self.msg_chan(name + "'s keys: " + str(keys))
          
    def delete_key(self, name, key):
        self.dbcursor.execute("select * from factoids where name=? and key=?", (name, key))
        factoids = self.dbcursor.fetchall()

        if not self.is_registered(name):
            self.msg_chan("You need to register and add your own factoids %s! Try: kazbot help" % name)
        elif not factoids:
            self.msg_chan("Key not found")
        else:
            self.dbcursor.execute("delete from factoids where name=? and key =?", (name, key))
            self.database.commit()
            self.msg_chan("Key succesfuly deleted")

    def is_registered(self, name):
        self.dbcursor.execute("select * from registered_users where name=?", (name,))
        matches = self.dbcursor.fetchall()
        if matches: return True
        else: return False

    def parse_buff(self, buff):
        if 'PRIVMSG' in buff or 'NOTICE' in buff:
            buff = buff.split()
            name = buff[0][1:buff[0].find('!')]
            buff[3] = buff[3].lstrip(':')
            args = buff[3:]
            self.process_command(name, args)

        elif 'PING' in buff:
            self.pingpong(buff)
            
    def process_command(self, name, args):
        if len(args) == 1 and args[0].startswith('~'): 
            self.get_factoid(name, args[0][1:])

        elif name == "NickServ" and args[1] == "ACC": 
            self.register_user(args) 

        elif 'kazbot' in args[0]:
            if len(args) > 3:
                if args[1] == "add-factoid": 
                    self.add_factoid(name, args[2:])
                    return

            if len(args) > 2:
                if args[1] == "sort":
                    self.msg_chan(string.join(sorted(args[2:])))
                    return
                elif args[1] == "say": 
                    self.msg_chan(string.join(args[2:]))
                    return
                elif args[1] == "delete-key":
                    self.delete_key(name, args[2])
                    return

            if len(args) > 1:
                if args[1] == "register": 
                    self.msg_user("NickServ", "ACC %s" % name)
                    return
                elif args[1] == "list-keys":
                    self.list_keys(name)
                    return
                elif args[1] == "help":
                    help_msg = ('Commands: register, add-factoid <key> '
                                '<factoid>, ~<factoid-key>, list-keys, '
                                'delete-key <key>, say <message>, '
                                'sort <data>')

                    self.msg_chan(help_msg)


    def main_loop(self):
        # Connect to database
        self.initialize_database()
        # self.database = sqlite3.connect('factoids.db')
        # self.dbcursor = self.database.cursor()

        # Connect to IRC channel
        self.connect()
        self.login()
        self.join_channel()

        while True:
            buff = self.IRC.recv(4096)
            if buff and self.debug: print "I< " + buff
            self.parse_buff(buff)

        self.database.close()
            

if __name__ == "__main__":
    kazbot = Kazbot()
    kazbot.main_loop()
