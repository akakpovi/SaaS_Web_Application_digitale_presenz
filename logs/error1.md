elom@elom-Latitude-E7470:~/Schreibtisch/SaaS_Web_Application_digitale_presenz/backend$ docker compose logs --tail=150 web
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/core/management/__init__.py", line 442, in execute_from_command_line
web-1  |     utility.execute()
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/core/management/__init__.py", line 436, in execute
web-1  |     self.fetch_command(subcommand).run_from_argv(self.argv)
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/core/management/base.py", line 420, in run_from_argv
web-1  |     self.execute(*args, **cmd_options)
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/core/management/base.py", line 464, in execute
web-1  |     output = self.handle(*args, **options)
web-1  |              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/core/management/base.py", line 111, in wrapper
web-1  |     res = handle_func(*args, **kwargs)
web-1  |           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/core/management/commands/migrate.py", line 114, in handle
web-1  |     executor = MigrationExecutor(connection, self.migration_progress_callback)
web-1  |                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/db/migrations/executor.py", line 18, in __init__
web-1  |     self.loader = MigrationLoader(self.connection)
web-1  |                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/db/migrations/loader.py", line 58, in __init__
web-1  |     self.build_graph()
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/db/migrations/loader.py", line 235, in build_graph
web-1  |     self.applied_migrations = recorder.applied_migrations()
web-1  |                               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/db/migrations/recorder.py", line 89, in applied_migrations
web-1  |     if self.has_table():
web-1  |        ^^^^^^^^^^^^^^^^
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/db/migrations/recorder.py", line 63, in has_table
web-1  |     with self.connection.cursor() as cursor:
web-1  |          ^^^^^^^^^^^^^^^^^^^^^^^^
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/utils/asyncio.py", line 26, in inner
web-1  |     return func(*args, **kwargs)
web-1  |            ^^^^^^^^^^^^^^^^^^^^^
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/db/backends/base/base.py", line 320, in cursor
web-1  |     return self._cursor()
web-1  |            ^^^^^^^^^^^^^^
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/db/backends/base/base.py", line 296, in _cursor
web-1  |     self.ensure_connection()
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/utils/asyncio.py", line 26, in inner
web-1  |     return func(*args, **kwargs)
web-1  |            ^^^^^^^^^^^^^^^^^^^^^
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/db/backends/base/base.py", line 278, in ensure_connection
web-1  |     with self.wrap_database_errors:
web-1  |          ^^^^^^^^^^^^^^^^^^^^^^^^^
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/db/utils.py", line 91, in __exit__
web-1  |     raise dj_exc_value.with_traceback(traceback) from exc_value
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/db/backends/base/base.py", line 279, in ensure_connection
web-1  |     self.connect()
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/utils/asyncio.py", line 26, in inner
web-1  |     return func(*args, **kwargs)
web-1  |            ^^^^^^^^^^^^^^^^^^^^^
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/db/backends/base/base.py", line 256, in connect
web-1  |     self.connection = self.get_new_connection(conn_params)
web-1  |                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/utils/asyncio.py", line 26, in inner
web-1  |     return func(*args, **kwargs)
web-1  |            ^^^^^^^^^^^^^^^^^^^^^
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/db/backends/postgresql/base.py", line 332, in get_new_connection
web-1  |     connection = self.Database.connect(**conn_params)
web-1  |                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
web-1  |   File "/usr/local/lib/python3.12/site-packages/psycopg/connection.py", line 120, in connect
web-1  |     raise last_ex.with_traceback(None)
web-1  | django.db.utils.OperationalError: connection failed: connection to server at "172.24.0.4", port 5432 failed: FATAL:  password authentication failed for user "presence"
web-1  | Traceback (most recent call last):
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/db/backends/base/base.py", line 279, in ensure_connection
web-1  |     self.connect()
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/utils/asyncio.py", line 26, in inner
web-1  |     return func(*args, **kwargs)
web-1  |            ^^^^^^^^^^^^^^^^^^^^^
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/db/backends/base/base.py", line 256, in connect
web-1  |     self.connection = self.get_new_connection(conn_params)
web-1  |                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/utils/asyncio.py", line 26, in inner
web-1  |     return func(*args, **kwargs)
web-1  |            ^^^^^^^^^^^^^^^^^^^^^
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/db/backends/postgresql/base.py", line 332, in get_new_connection
web-1  |     connection = self.Database.connect(**conn_params)
web-1  |                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
web-1  |   File "/usr/local/lib/python3.12/site-packages/psycopg/connection.py", line 120, in connect
web-1  |     raise last_ex.with_traceback(None)
web-1  | psycopg.OperationalError: connection failed: connection to server at "172.24.0.4", port 5432 failed: FATAL:  password authentication failed for user "presence"
web-1  | 
web-1  | The above exception was the direct cause of the following exception:
web-1  | 
web-1  | Traceback (most recent call last):
web-1  |   File "/app/manage.py", line 16, in <module>
web-1  |     main()
web-1  |   File "/app/manage.py", line 12, in main
web-1  |     execute_from_command_line(sys.argv)
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/core/management/__init__.py", line 442, in execute_from_command_line
web-1  |     utility.execute()
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/core/management/__init__.py", line 436, in execute
web-1  |     self.fetch_command(subcommand).run_from_argv(self.argv)
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/core/management/base.py", line 420, in run_from_argv
web-1  |     self.execute(*args, **cmd_options)
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/core/management/base.py", line 464, in execute
web-1  |     output = self.handle(*args, **options)
web-1  |              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/core/management/base.py", line 111, in wrapper
web-1  |     res = handle_func(*args, **kwargs)
web-1  |           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/core/management/commands/migrate.py", line 114, in handle
web-1  |     executor = MigrationExecutor(connection, self.migration_progress_callback)
web-1  |                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/db/migrations/executor.py", line 18, in __init__
web-1  |     self.loader = MigrationLoader(self.connection)
web-1  |                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/db/migrations/loader.py", line 58, in __init__
web-1  |     self.build_graph()
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/db/migrations/loader.py", line 235, in build_graph
web-1  |     self.applied_migrations = recorder.applied_migrations()
web-1  |                               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/db/migrations/recorder.py", line 89, in applied_migrations
web-1  |     if self.has_table():
web-1  |        ^^^^^^^^^^^^^^^^
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/db/migrations/recorder.py", line 63, in has_table
web-1  |     with self.connection.cursor() as cursor:
web-1  |          ^^^^^^^^^^^^^^^^^^^^^^^^
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/utils/asyncio.py", line 26, in inner
web-1  |     return func(*args, **kwargs)
web-1  |            ^^^^^^^^^^^^^^^^^^^^^
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/db/backends/base/base.py", line 320, in cursor
web-1  |     return self._cursor()
web-1  |            ^^^^^^^^^^^^^^
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/db/backends/base/base.py", line 296, in _cursor
web-1  |     self.ensure_connection()
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/utils/asyncio.py", line 26, in inner
web-1  |     return func(*args, **kwargs)
web-1  |            ^^^^^^^^^^^^^^^^^^^^^
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/db/backends/base/base.py", line 278, in ensure_connection
web-1  |     with self.wrap_database_errors:
web-1  |          ^^^^^^^^^^^^^^^^^^^^^^^^^
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/db/utils.py", line 91, in __exit__
web-1  |     raise dj_exc_value.with_traceback(traceback) from exc_value
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/db/backends/base/base.py", line 279, in ensure_connection
web-1  |     self.connect()
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/utils/asyncio.py", line 26, in inner
web-1  |     return func(*args, **kwargs)
web-1  |            ^^^^^^^^^^^^^^^^^^^^^
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/db/backends/base/base.py", line 256, in connect
web-1  |     self.connection = self.get_new_connection(conn_params)
web-1  |                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/utils/asyncio.py", line 26, in inner
web-1  |     return func(*args, **kwargs)
web-1  |            ^^^^^^^^^^^^^^^^^^^^^
web-1  |   File "/usr/local/lib/python3.12/site-packages/django/db/backends/postgresql/base.py", line 332, in get_new_connection
web-1  |     connection = self.Database.connect(**conn_params)
web-1  |                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
web-1  |   File "/usr/local/lib/python3.12/site-packages/psycopg/connection.py", line 120, in connect
web-1  |     raise last_ex.with_traceback(None)
web-1  | django.db.utils.OperationalError: connection failed: connection to server at "172.24.0.4", port 5432 failed: FATAL:  password authentication failed for user "presence"
elom@elom-Latitude-E7470:~/Schreibtisch/SaaS_Web_Application_digitale_presenz/backend$ docker inspect backend-web-1 --format '{{json .State}}'
{"Status":"restarting","Running":true,"Paused":false,"Restarting":true,"OOMKilled":false,"Dead":false,"Pid":0,"ExitCode":1,"Error":"","StartedAt":"2026-08-22T08:55:38.409675072Z","FinishedAt":"2026-08-22T08:55:41.160084919Z","Health":{"Status":"unhealthy","FailingStreak":0,"Log":[]}}
elom@elom-Latitude-E7470:~/Schreibtisch/SaaS_Web_Application_digitale_presenz/backend$ docker inspect backend-web-1 --format '{{json .Config.Healthcheck}}'
{"Test":["CMD","python","-c","import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/', timeout=5)"],"Interval":30000000000,"Timeout":10000000000,"StartPeriod":30000000000,"Retries":5}
elom@elom-Latitude-E7470:~/Schreibtisch/SaaS_Web_Application_digitale_presenz/backend$ docker compose ps
NAME                      IMAGE                   COMMAND                  SERVICE         CREATED         STATUS                          PORTS
backend-celery-beat-1     backend-celery-beat     "celery -A config be…"   celery-beat     3 minutes ago   Up 3 minutes                    8000/tcp
backend-celery-worker-1   backend-celery-worker   "celery -A config wo…"   celery-worker   3 minutes ago   Up 3 minutes                    8000/tcp
backend-db-1              postgres:16-alpine      "docker-entrypoint.s…"   db              3 minutes ago   Up 3 minutes (healthy)          5432/tcp
backend-redis-1           redis:7-alpine          "docker-entrypoint.s…"   redis           2 hours ago     Up 2 hours (healthy)            6379/tcp
backend-web-1             backend-web             "sh -c 'python manag…"   web             3 minutes ago   Restarting (1) 55 seconds ago   
elom@elom-Latitude-E7470:~/Schreibtisch/SaaS_Web_Application_digitale_presenz/backend$ 

