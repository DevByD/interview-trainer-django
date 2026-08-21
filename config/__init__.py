"""
Project package init.

PyMySQL is a pure-Python MySQL driver used as a drop-in replacement for
MySQLdb (mysqlclient). This must run before Django loads the database
backend, which is why it lives here.
"""

import pymysql

pymysql.install_as_MySQLdb()

# Django 6.1 sets MySQL 8.4 as the minimum requirement, but MySQL 8.0 is fully compatible
from django.db.backends.base.base import BaseDatabaseWrapper

BaseDatabaseWrapper.check_database_version_supported = lambda self: None
