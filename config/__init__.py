"""Project package init.

Optional pure-Python MySQL driver support. If pymysql is installed and MySQL is used,
it registers as a drop-in replacement for MySQLdb.
"""

try:
    import pymysql

    pymysql.install_as_MySQLdb()
    from django.db.backends.base.base import BaseDatabaseWrapper

    BaseDatabaseWrapper.check_database_version_supported = lambda self: None
except ImportError:
    pass
