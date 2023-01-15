# pyright: reportGeneralTypeIssues=false

import os
from .payload import Payload
from datetime import datetime
from conf import Configuration  # type: ignore
from tinydb import TinyDB, Query
from tinydb.operations import delete


class Model:
    """
    Object for interact with database with pre-defined function
    """

    def __init__(self, conf=Configuration, init=True):
        """
        object to interact with database

        @params: conf [ Configuration object ]
        @return: Request object
        """
        if not init:
            return

        self.ADAPTER = conf.ADAPTER
        if self.ADAPTER in ("MYSQL", "POSTGRESQL"):
            self.DB_CONF = {
                "host": conf.DB_HOST,
                "user": conf.DB_USER,
                "password": conf.DB_PASSWORD,
                "database": conf.DB_NAME,
            }
            if conf.DB_PORT:
                self.DB_CONF["port"] = conf.DB_PORT
        elif self.ADAPTER == "MONGODB":
            self.DB_CONF = "mongodb" + ("://" if conf.DB_PORT else "+srv://")
            if conf.DB_USER and conf.DB_PASSWORD:
                self.DB_CONF += conf.DB_USER + ":" + conf.DB_PASSWORD + "@"
            self.DB_CONF += conf.DB_HOST
            if conf.DB_PORT:
                self.DB_CONF += ":" + str(conf.DB_PORT) + "/"
        else:  # SQLite is choosen by default
            self.DB_CONF = conf.DB_FILE

        self.__connect()
        self.__init_db()
        os.makedirs("assets/private/", exist_ok=True)
        self.tinydb = TinyDB("assets/private/_db.json")

    def __connect(self):
        """
        The function which connect object to the database.
        """
        if self.ADAPTER == "MYSQL":
            import mysql.connector

            self.db = mysql.connector.connect(**self.DB_CONF)
        elif self.ADAPTER == "POSTGRESQL":
            import psycopg2

            self.db = psycopg2.connect(**self.DB_CONF)
        elif self.ADAPTER == "MONGODB":
            import pymongo

            self.db = pymongo.MongoClient(self.DB_CONF)
            self.db = self.db[Configuration.DB_NAME]
            return
        else:
            import sqlite3

            self.db = sqlite3.connect(
                self.DB_CONF,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
            )

        self.cursor = self.db.cursor()

    def __init_db(self):
        """
        Creation of table if not exist
        Check the necessary table if exists
        """

        if self.ADAPTER == "MYSQL":
            req = """
                CREATE TABLE IF NOT EXISTS `amp_user` (
                    `id` INT NOT NULL AUTO_INCREMENT,
                    `sender_id` varchar(50) NOT NULL UNIQUE,
                    `action` TEXT DEFAULT NULL,
                    `last_use` datetime NOT NULL DEFAULT current_timestamp(),
                    `lang` varchar(5) DEFAULT NULL,
                    PRIMARY KEY (`id`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        elif self.ADAPTER == "POSTGRESQL":
            req = """
                CREATE TABLE IF NOT EXISTS  "amp_user" (
                    id SERIAL,
                    sender_id VARCHAR NULL DEFAULT NULL,
                    action TEXT NULL DEFAULT NULL,
                    last_use TIMESTAMP NULL DEFAULT NOW(),
                    lang VARCHAR NULL DEFAULT NULL,
                    PRIMARY KEY (id),
                    UNIQUE (sender_id)
                )
            """
        elif self.ADAPTER == "MONGODB":
            if "amp_user" not in self.db.list_collection_names():
                self.db.create_collection("amp_user")
                # self.db.amp_user.create_index("sender_id", unique=True)
            return
        else:
            req = """
               CREATE TABLE IF NOT EXISTS amp_user (
                   id INTEGER PRIMARY KEY AUTOINCREMENT, 
                   sender_id TEXT NOT NULL UNIQUE,
                   action TEXT,
                   last_use TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                   lang TEXT
                )
            """
        self.cursor.execute(req)
        self.db.commit()

    def verif_db(fonction):  # type: ignore
        """
        decorator that checks if the database
        is connected or not before doing an operation.
        """

        def trt_verif(*arg, **kwarg):
            arg[0].__connect()
            return fonction(*arg, **kwarg)

        return trt_verif

    @verif_db
    def _verif_user(self, sender_id):
        """
        method to insert new user and/or update the date
        of last use if the user already exists.

        @params :  sender_id

        """
        # Insertion dans la base si non present
        # Mise à jour du last_use si déja présent
        if self.ADAPTER == "MYSQL":
            req = """
                INSERT INTO amp_user(sender_id) VALUES (%s)
                ON DUPLICATE KEY UPDATE last_use = NOW()
            """
        elif self.ADAPTER == "POSTGRESQL":
            req = """
                INSERT INTO amp_user(sender_id) VALUES (%s)
                ON CONFLICT (sender_id) DO UPDATE SET last_use = NOW();
            """
        elif self.ADAPTER == "MONGODB":
            self.db.amp_user.update_one(
                {"sender_id": sender_id},
                {"$set": {"last_use": datetime.now()}},
                upsert=True,
            )
            return
        else:
            req = """
                INSERT INTO amp_user(sender_id) VALUES (?)
                ON CONFLICT(sender_id) DO UPDATE SET last_use = CURRENT_TIMESTAMP;
            """
        self.cursor.execute(req, (sender_id,))
        self.db.commit()

    @verif_db
    def get_action(self, sender_id):
        """
        get current action of an user

         @params :  sender_id
         @return : current action [ type of String/None ]
        """
        if self.ADAPTER in ("MYSQL", "POSTGRESQL"):
            req = "SELECT action FROM amp_user WHERE sender_id = %s"
        elif self.ADAPTER == "MONGODB":
            return self.db.amp_user.find({"sender_id": sender_id})[0].get("action")
        else:
            req = "SELECT action FROM amp_user WHERE sender_id = ?"
        self.cursor.execute(req, (sender_id,))
        # retourne le resultat
        return self.cursor.fetchone()[0]

    @verif_db
    def set_action(self, sender_id, action):
        """
        define a current action if an user

        @params :  sender_id, action
        @return:  None
        """
        if isinstance(action, Payload):
            action = Payload.trt_payload_out(action)

        if self.ADAPTER in ("MYSQL", "POSTGRESQL"):
            req = "UPDATE amp_user set action = %s WHERE sender_id = %s"
        elif self.ADAPTER == "MONGODB":
            self.db.amp_user.update_one(
                {"sender_id": sender_id},
                {"$set": {"action": action}},
            )
            return
        else:
            req = "UPDATE amp_user set action = ? WHERE sender_id = ?"
        self.cursor.execute(req, (action, sender_id))
        self.db.commit()

    @verif_db
    def set_temp(self, sender_id, key, value):
        """
        set a temp parameter of an user

         @params:  sender_id
         @return:  None
        """
        if self.ADAPTER == "MONGODB":
            self.db.amp_user.update_one(
                {"sender_id": sender_id},
                {"$set": {key: value}},
            )
            return
        if not self.tinydb.update({key: value}, Query().sender_id == sender_id):
            self.tinydb.insert({"sender_id": sender_id, key: value})

    @verif_db
    def get_temp(self, sender_id, key):
        """
        get one temporary data of an user

        @parmas :  sender_id
                   key
        @return: data
        """
        if self.ADAPTER == "MONGODB":
            return self.db.amp_user.find({"sender_id": sender_id})[0].get(key)

        res = self.tinydb.search(Query().sender_id == sender_id)
        if res:
            return res[0].get(key)

    @verif_db
    def del_temp(self, sender_id, key):
        """
        delete temporary parameter of an user

        @parameter :  sender_id
                      key
        @return: None
        """
        if self.ADAPTER == "MONGODB":
            self.db.amp_user.update_one(
                {"sender_id": sender_id},
                {"$unset": {key: ""}},
            )
            return
        self.tinydb.update(delete(key), Query().sender_id == sender_id)

    @verif_db
    def get_lang(self, sender_id):
        """
        get current lang of an user

        @params: sender_id
        @return lang or None
        """

        if self.ADAPTER in ("MYSQL", "POSTGRESQL"):
            req = "SELECT lang FROM amp_user WHERE sender_id = %s"
        elif self.ADAPTER == "MONGODB":
            return self.db.amp_user.find({"sender_id": sender_id})[0].get("lang")
        else:
            req = "SELECT lang FROM amp_user WHERE sender_id = ?"
        self.cursor.execute(req, (sender_id,))
        return self.cursor.fetchone()[0]

    @verif_db
    def set_lang(self, sender_id, lang):
        """
        define a current lang for an user

        @params :  sender_id
        @return:  None
        """
        if self.ADAPTER in ("MYSQL", "POSTGRESQL"):
            req = "UPDATE amp_user set lang = %s WHERE sender_id = %s"
        elif self.ADAPTER == "MONGODB":
            self.db.amp_user.update_one(
                {"sender_id": sender_id},
                {"$set": {"lang": lang}},
            )
            return
        else:
            req = "UPDATE amp_user set lang = ? WHERE sender_id = ?"
        self.cursor.execute(req, (lang, sender_id))
        self.db.commit()

    @verif_db
    def get(self, sender_id, *args):
        """
        get specific data of an user

        @params :  sender_id, list of data to get
        @return:  list of data
        """
        if self.ADAPTER in ("MYSQL", "POSTGRESQL"):
            req = f"SELECT {','.join(args)} FROM amp_user WHERE sender_id = %s"
        elif self.ADAPTER == "MONGODB":
            data = self.db.amp_user.find({"sender_id": sender_id})[0]
            return [data.get(k) for k in args]
        else:
            req = f"SELECT {','.join(args)} FROM amp_user WHERE sender_id = ?"
        self.cursor.execute(req, (sender_id,))
        return self.cursor.fetchone()
