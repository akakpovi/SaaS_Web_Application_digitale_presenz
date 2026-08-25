elom@elom-Latitude-E7470:~/Schreibtisch/SaaS_Web_Application_digitale_presenz/backend$ docker compose down
[+] down 8/8
 ✔ Container backend-nginx-1         Removed                                                                                                                                                                                            0.0s
 ✔ Container backend-celery-beat-1   Removed                                                                                                                                                                                            0.4s
 ✔ Container backend-celery-worker-1 Removed                                                                                                                                                                                            2.2s
 ✔ Container backend-web-1           Removed                                                                                                                                                                                            0.0s
 ✔ Container backend-staticfiles-1   Removed                                                                                                                                                                                            0.0s
 ✔ Container backend-redis-1         Removed                                                                                                                                                                                            0.3s
 ✔ Container backend-db-1            Removed                                                                                                                                                                                            0.3s
 ✔ Network backend_default           Removed                                                                                                                                                                                            0.1s
elom@elom-Latitude-E7470:~/Schreibtisch/SaaS_Web_Application_digitale_presenz/backend$ docker volume ls | grep backend
local     backend_postgres_data
local     backend_redis_data
local     backend_static_data
elom@elom-Latitude-E7470:~/Schreibtisch/SaaS_Web_Application_digitale_presenz/backend$ docker compose down -v
[+] down 3/3
 ✔ Volume backend_postgres_data Removed                                                                                                                                                                                                 0.0s
 ✔ Volume backend_redis_data    Removed                                                                                                                                                                                                 0.0s
 ✔ Volume backend_static_data   Removed                                                                                                                                                                                                 0.0s
elom@elom-Latitude-E7470:~/Schreibtisch/SaaS_Web_Application_digitale_presenz/backend$ docker compose down
docker volume ls | grep backend
elom@elom-Latitude-E7470:~/Schreibtisch/SaaS_Web_Application_digitale_presenz/backend$ docker compose up -d
[+] up 11/11
 ✔ Network backend_default           Created                                                                                                                                                                                            0.1s
 ✔ Volume backend_postgres_data      Created                                                                                                                                                                                            0.0s
 ✔ Volume backend_redis_data         Created                                                                                                                                                                                            0.0s
 ✔ Volume backend_static_data        Created                                                                                                                                                                                            0.0s
 ✔ Container backend-staticfiles-1   Exited                                                                                                                                                                                             3.4s
 ✔ Container backend-db-1            Healthy                                                                                                                                                                                           11.3s
 ✔ Container backend-redis-1         Healthy                                                                                                                                                                                           11.3s
 ✔ Container backend-web-1           Healthy                                                                                                                                                                                           19.3s
 ✔ Container backend-celery-worker-1 Started                                                                                                                                                                                           11.8s
 ✔ Container backend-celery-beat-1   Started                                                                                                                                                                                           11.8s
 ✔ Container backend-nginx-1         Started                                                                                                                                                                                           19.6s
elom@elom-Latitude-E7470:~/Schreibtisch/SaaS_Web_Application_digitale_presenz/backend$ docker compose ps
NAME                      IMAGE                   COMMAND                  SERVICE         CREATED         STATUS                   PORTS
backend-celery-beat-1     backend-celery-beat     "celery -A config be…"   celery-beat     3 minutes ago   Up 3 minutes             8000/tcp
backend-celery-worker-1   backend-celery-worker   "celery -A config wo…"   celery-worker   3 minutes ago   Up 3 minutes             8000/tcp
backend-db-1              postgres:16-alpine      "docker-entrypoint.s…"   db              3 minutes ago   Up 3 minutes (healthy)   5432/tcp
backend-nginx-1           nginx:1.27-alpine       "/docker-entrypoint.…"   nginx           3 minutes ago   Up 3 minutes (healthy)   0.0.0.0:8080->80/tcp, [::]:8080->80/tcp
backend-redis-1           redis:7-alpine          "docker-entrypoint.s…"   redis           3 minutes ago   Up 3 minutes (healthy)   6379/tcp
backend-web-1             backend-web             "sh -c 'python manag…"   web             3 minutes ago   Up 3 minutes (healthy)   8000/tcp
elom@elom-Latitude-E7470:~/Schreibtisch/SaaS_Web_Application_digitale_presenz/backend$ docker compose logs --tail=100 web
web-1  | Operations to perform:
web-1  |   Apply all migrations: accounts, admin, auth, contenttypes, scans, sessions, token_blacklist, websites
web-1  | Running migrations:
web-1  |   Applying contenttypes.0001_initial... OK
web-1  |   Applying contenttypes.0002_remove_content_type_name... OK
web-1  |   Applying auth.0001_initial... OK
web-1  |   Applying auth.0002_alter_permission_name_max_length... OK
web-1  |   Applying auth.0003_alter_user_email_max_length... OK
web-1  |   Applying auth.0004_alter_user_username_opts... OK
web-1  |   Applying auth.0005_alter_user_last_login_null... OK
web-1  |   Applying auth.0006_require_contenttypes_0002... OK
web-1  |   Applying auth.0007_alter_validators_add_error_messages... OK
web-1  |   Applying auth.0008_alter_user_username_max_length... OK
web-1  |   Applying auth.0009_alter_user_last_name_max_length... OK
web-1  |   Applying auth.0010_alter_group_name_max_length... OK
web-1  |   Applying auth.0011_update_proxy_permissions... OK
web-1  |   Applying auth.0012_alter_user_first_name_max_length... OK
web-1  |   Applying accounts.0001_initial... OK
web-1  |   Applying admin.0001_initial... OK
web-1  |   Applying admin.0002_logentry_remove_auto_add... OK
web-1  |   Applying admin.0003_logentry_add_action_flag_choices... OK
web-1  |   Applying websites.0001_initial... OK
web-1  |   Applying scans.0001_initial... OK
web-1  |   Applying sessions.0001_initial... OK
web-1  |   Applying token_blacklist.0001_initial... OK
web-1  |   Applying token_blacklist.0002_outstandingtoken_jti_hex... OK
web-1  |   Applying token_blacklist.0003_auto_20171017_2007... OK
web-1  |   Applying token_blacklist.0004_auto_20171017_2013... OK
web-1  |   Applying token_blacklist.0005_remove_outstandingtoken_jti... OK
web-1  |   Applying token_blacklist.0006_auto_20171017_2113... OK
web-1  |   Applying token_blacklist.0007_auto_20171017_2214... OK
web-1  |   Applying token_blacklist.0008_migrate_to_bigautofield... OK
web-1  |   Applying token_blacklist.0010_fix_migrate_to_bigautofield... OK
web-1  |   Applying token_blacklist.0011_linearizes_history... OK
web-1  |   Applying token_blacklist.0012_alter_outstandingtoken_user... OK
web-1  |   Applying token_blacklist.0013_alter_blacklistedtoken_options_and_more... OK
web-1  | [2026-08-22 09:18:48 +0000] [8] [INFO] Starting gunicorn 23.0.0
web-1  | [2026-08-22 09:18:48 +0000] [8] [INFO] Listening at: http://0.0.0.0:8000 (8)
web-1  | [2026-08-22 09:18:48 +0000] [8] [INFO] Using worker: sync
web-1  | [2026-08-22 09:18:48 +0000] [15] [INFO] Booting worker with pid: 15
web-1  | [2026-08-22 09:18:48 +0000] [16] [INFO] Booting worker with pid: 16
web-1  | [2026-08-22 09:18:48 +0000] [17] [INFO] Booting worker with pid: 17
web-1  | 127.0.0.1 - - [22/Aug/2026:09:18:50 +0000] "GET /api/v1/health/ HTTP/1.1" 200 86 "-" "Python-urllib/3.12"
web-1  | 127.0.0.1 - - [22/Aug/2026:09:19:21 +0000] "GET /api/v1/health/ HTTP/1.1" 200 86 "-" "Python-urllib/3.12"
web-1  | 172.24.0.7 - - [22/Aug/2026:09:19:21 +0000] "GET /api/v1/health/ HTTP/1.1" 200 86 "-" "Wget"
web-1  | 172.24.0.7 - - [22/Aug/2026:09:19:51 +0000] "GET /api/v1/health/ HTTP/1.1" 200 86 "-" "Wget"
web-1  | 127.0.0.1 - - [22/Aug/2026:09:19:51 +0000] "GET /api/v1/health/ HTTP/1.1" 200 86 "-" "Python-urllib/3.12"
web-1  | 172.24.0.7 - - [22/Aug/2026:09:20:21 +0000] "GET /api/v1/health/ HTTP/1.1" 200 86 "-" "Wget"
web-1  | 127.0.0.1 - - [22/Aug/2026:09:20:22 +0000] "GET /api/v1/health/ HTTP/1.1" 200 86 "-" "Python-urllib/3.12"
web-1  | 172.24.0.7 - - [22/Aug/2026:09:20:51 +0000] "GET /api/v1/health/ HTTP/1.1" 200 86 "-" "Wget"
web-1  | 127.0.0.1 - - [22/Aug/2026:09:20:52 +0000] "GET /api/v1/health/ HTTP/1.1" 200 86 "-" "Python-urllib/3.12"
web-1  | 172.24.0.7 - - [22/Aug/2026:09:21:21 +0000] "GET /api/v1/health/ HTTP/1.1" 200 86 "-" "Wget"
web-1  | 127.0.0.1 - - [22/Aug/2026:09:21:23 +0000] "GET /api/v1/health/ HTTP/1.1" 200 86 "-" "Python-urllib/3.12"
web-1  | 172.24.0.7 - - [22/Aug/2026:09:21:52 +0000] "GET /api/v1/health/ HTTP/1.1" 200 86 "-" "Wget"
web-1  | 127.0.0.1 - - [22/Aug/2026:09:21:53 +0000] "GET /api/v1/health/ HTTP/1.1" 200 86 "-" "Python-urllib/3.12"
web-1  | 172.24.0.7 - - [22/Aug/2026:09:22:22 +0000] "GET /api/v1/health/ HTTP/1.1" 200 86 "-" "Wget"
web-1  | 127.0.0.1 - - [22/Aug/2026:09:22:24 +0000] "GET /api/v1/health/ HTTP/1.1" 200 86 "-" "Python-urllib/3.12"
elom@elom-Latitude-E7470:~/Schreibtisch/SaaS_Web_Application_digitale_presenz/backend$ docker compose logs --tail=100 web
web-1  | Operations to perform:
web-1  |   Apply all migrations: accounts, admin, auth, contenttypes, scans, sessions, token_blacklist, websites
web-1  | Running migrations:
web-1  |   Applying contenttypes.0001_initial... OK
web-1  |   Applying contenttypes.0002_remove_content_type_name... OK
web-1  |   Applying auth.0001_initial... OK
web-1  |   Applying auth.0002_alter_permission_name_max_length... OK
web-1  |   Applying auth.0003_alter_user_email_max_length... OK
web-1  |   Applying auth.0004_alter_user_username_opts... OK
web-1  |   Applying auth.0005_alter_user_last_login_null... OK
web-1  |   Applying auth.0006_require_contenttypes_0002... OK
web-1  |   Applying auth.0007_alter_validators_add_error_messages... OK
web-1  |   Applying auth.0008_alter_user_username_max_length... OK
web-1  |   Applying auth.0009_alter_user_last_name_max_length... OK
web-1  |   Applying auth.0010_alter_group_name_max_length... OK
web-1  |   Applying auth.0011_update_proxy_permissions... OK
web-1  |   Applying auth.0012_alter_user_first_name_max_length... OK
web-1  |   Applying accounts.0001_initial... OK
web-1  |   Applying admin.0001_initial... OK
web-1  |   Applying admin.0002_logentry_remove_auto_add... OK
web-1  |   Applying admin.0003_logentry_add_action_flag_choices... OK
web-1  |   Applying websites.0001_initial... OK
web-1  |   Applying scans.0001_initial... OK
web-1  |   Applying sessions.0001_initial... OK
web-1  |   Applying token_blacklist.0001_initial... OK
web-1  |   Applying token_blacklist.0002_outstandingtoken_jti_hex... OK
web-1  |   Applying token_blacklist.0003_auto_20171017_2007... OK
web-1  |   Applying token_blacklist.0004_auto_20171017_2013... OK
web-1  |   Applying token_blacklist.0005_remove_outstandingtoken_jti... OK
web-1  |   Applying token_blacklist.0006_auto_20171017_2113... OK
web-1  |   Applying token_blacklist.0007_auto_20171017_2214... OK
web-1  |   Applying token_blacklist.0008_migrate_to_bigautofield... OK
web-1  |   Applying token_blacklist.0010_fix_migrate_to_bigautofield... OK
web-1  |   Applying token_blacklist.0011_linearizes_history... OK
web-1  |   Applying token_blacklist.0012_alter_outstandingtoken_user... OK
web-1  |   Applying token_blacklist.0013_alter_blacklistedtoken_options_and_more... OK
web-1  | [2026-08-22 09:18:48 +0000] [8] [INFO] Starting gunicorn 23.0.0
web-1  | [2026-08-22 09:18:48 +0000] [8] [INFO] Listening at: http://0.0.0.0:8000 (8)
web-1  | [2026-08-22 09:18:48 +0000] [8] [INFO] Using worker: sync
web-1  | [2026-08-22 09:18:48 +0000] [15] [INFO] Booting worker with pid: 15
web-1  | [2026-08-22 09:18:48 +0000] [16] [INFO] Booting worker with pid: 16
web-1  | [2026-08-22 09:18:48 +0000] [17] [INFO] Booting worker with pid: 17
web-1  | 127.0.0.1 - - [22/Aug/2026:09:18:50 +0000] "GET /api/v1/health/ HTTP/1.1" 200 86 "-" "Python-urllib/3.12"
web-1  | 127.0.0.1 - - [22/Aug/2026:09:19:21 +0000] "GET /api/v1/health/ HTTP/1.1" 200 86 "-" "Python-urllib/3.12"
web-1  | 172.24.0.7 - - [22/Aug/2026:09:19:21 +0000] "GET /api/v1/health/ HTTP/1.1" 200 86 "-" "Wget"
web-1  | 172.24.0.7 - - [22/Aug/2026:09:19:51 +0000] "GET /api/v1/health/ HTTP/1.1" 200 86 "-" "Wget"
web-1  | 127.0.0.1 - - [22/Aug/2026:09:19:51 +0000] "GET /api/v1/health/ HTTP/1.1" 200 86 "-" "Python-urllib/3.12"
web-1  | 172.24.0.7 - - [22/Aug/2026:09:20:21 +0000] "GET /api/v1/health/ HTTP/1.1" 200 86 "-" "Wget"
web-1  | 127.0.0.1 - - [22/Aug/2026:09:20:22 +0000] "GET /api/v1/health/ HTTP/1.1" 200 86 "-" "Python-urllib/3.12"
web-1  | 172.24.0.7 - - [22/Aug/2026:09:20:51 +0000] "GET /api/v1/health/ HTTP/1.1" 200 86 "-" "Wget"
web-1  | 127.0.0.1 - - [22/Aug/2026:09:20:52 +0000] "GET /api/v1/health/ HTTP/1.1" 200 86 "-" "Python-urllib/3.12"
web-1  | 172.24.0.7 - - [22/Aug/2026:09:21:21 +0000] "GET /api/v1/health/ HTTP/1.1" 200 86 "-" "Wget"
web-1  | 127.0.0.1 - - [22/Aug/2026:09:21:23 +0000] "GET /api/v1/health/ HTTP/1.1" 200 86 "-" "Python-urllib/3.12"
web-1  | 172.24.0.7 - - [22/Aug/2026:09:21:52 +0000] "GET /api/v1/health/ HTTP/1.1" 200 86 "-" "Wget"
web-1  | 127.0.0.1 - - [22/Aug/2026:09:21:53 +0000] "GET /api/v1/health/ HTTP/1.1" 200 86 "-" "Python-urllib/3.12"
web-1  | 172.24.0.7 - - [22/Aug/2026:09:22:22 +0000] "GET /api/v1/health/ HTTP/1.1" 200 86 "-" "Wget"
web-1  | 127.0.0.1 - - [22/Aug/2026:09:22:24 +0000] "GET /api/v1/health/ HTTP/1.1" 200 86 "-" "Python-urllib/3.12"
web-1  | 172.24.0.7 - - [22/Aug/2026:09:22:52 +0000] "GET /api/v1/health/ HTTP/1.1" 200 86 "-" "Wget"
web-1  | 127.0.0.1 - - [22/Aug/2026:09:22:54 +0000] "GET /api/v1/health/ HTTP/1.1" 200 86 "-" "Python-urllib/3.12"
elom@elom-Latitude-E7470:~/Schreibtisch/SaaS_Web_Application_digitale_presenz/backend$ docker compose logs --tail=100 nginx
nginx-1  | /docker-entrypoint.sh: /docker-entrypoint.d/ is not empty, will attempt to perform configuration
nginx-1  | /docker-entrypoint.sh: Looking for shell scripts in /docker-entrypoint.d/
nginx-1  | /docker-entrypoint.sh: Launching /docker-entrypoint.d/10-listen-on-ipv6-by-default.sh
nginx-1  | 10-listen-on-ipv6-by-default.sh: info: can not modify /etc/nginx/conf.d/default.conf (read-only file system?)
nginx-1  | /docker-entrypoint.sh: Sourcing /docker-entrypoint.d/15-local-resolvers.envsh
nginx-1  | /docker-entrypoint.sh: Launching /docker-entrypoint.d/20-envsubst-on-templates.sh
nginx-1  | /docker-entrypoint.sh: Launching /docker-entrypoint.d/30-tune-worker-processes.sh
nginx-1  | /docker-entrypoint.sh: Configuration complete; ready for start up
nginx-1  | 2026/08/22 09:18:51 [notice] 1#1: using the "epoll" event method
nginx-1  | 2026/08/22 09:18:51 [notice] 1#1: nginx/1.27.5
nginx-1  | 2026/08/22 09:18:51 [notice] 1#1: built by gcc 14.2.0 (Alpine 14.2.0) 
nginx-1  | 2026/08/22 09:18:51 [notice] 1#1: OS: Linux 6.14.0-37-generic
nginx-1  | 2026/08/22 09:18:51 [notice] 1#1: getrlimit(RLIMIT_NOFILE): 1024:524288
nginx-1  | 2026/08/22 09:18:51 [notice] 1#1: start worker processes
nginx-1  | 2026/08/22 09:18:51 [notice] 1#1: start worker process 21
nginx-1  | 2026/08/22 09:18:51 [notice] 1#1: start worker process 22
nginx-1  | 2026/08/22 09:18:51 [notice] 1#1: start worker process 23
nginx-1  | 2026/08/22 09:18:51 [notice] 1#1: start worker process 24
nginx-1  | 127.0.0.1 - - [22/Aug/2026:09:19:21 +0000] "GET /api/v1/health/ HTTP/1.1" 200 86 "-" "Wget" "-"
nginx-1  | 127.0.0.1 - - [22/Aug/2026:09:19:51 +0000] "GET /api/v1/health/ HTTP/1.1" 200 86 "-" "Wget" "-"
nginx-1  | 127.0.0.1 - - [22/Aug/2026:09:20:21 +0000] "GET /api/v1/health/ HTTP/1.1" 200 86 "-" "Wget" "-"
nginx-1  | 127.0.0.1 - - [22/Aug/2026:09:20:51 +0000] "GET /api/v1/health/ HTTP/1.1" 200 86 "-" "Wget" "-"
nginx-1  | 127.0.0.1 - - [22/Aug/2026:09:21:21 +0000] "GET /api/v1/health/ HTTP/1.1" 200 86 "-" "Wget" "-"
nginx-1  | 127.0.0.1 - - [22/Aug/2026:09:21:52 +0000] "GET /api/v1/health/ HTTP/1.1" 200 86 "-" "Wget" "-"
nginx-1  | 127.0.0.1 - - [22/Aug/2026:09:22:22 +0000] "GET /api/v1/health/ HTTP/1.1" 200 86 "-" "Wget" "-"
nginx-1  | 127.0.0.1 - - [22/Aug/2026:09:22:52 +0000] "GET /api/v1/health/ HTTP/1.1" 200 86 "-" "Wget" "-"
nginx-1  | 127.0.0.1 - - [22/Aug/2026:09:23:22 +0000] "GET /api/v1/health/ HTTP/1.1" 200 86 "-" "Wget" "-"
elom@elom-Latitude-E7470:~/Schreibtisch/SaaS_Web_Application_digitale_presenz/backend$ docker compose logs --tail=100 celery-worker
celery-worker-1  |  
celery-worker-1  |  -------------- celery@8fd3ebc1ff06 v5.5.3 (immunity)
celery-worker-1  | --- ***** ----- 
celery-worker-1  | -- ******* ---- Linux-6.14.0-37-generic-x86_64-with-glibc2.41 2026-08-22 09:18:46
celery-worker-1  | - *** --- * --- 
celery-worker-1  | - ** ---------- [config]
celery-worker-1  | - ** ---------- .> app:         presence:0x7f99e11b05c0
celery-worker-1  | - ** ---------- .> transport:   redis://redis:6379/1
celery-worker-1  | - ** ---------- .> results:     redis://redis:6379/2
celery-worker-1  | - *** --- * --- .> concurrency: 4 (prefork)
celery-worker-1  | -- ******* ---- .> task events: OFF (enable -E to monitor tasks in this worker)
celery-worker-1  | --- ***** ----- 
celery-worker-1  |  -------------- [queues]
celery-worker-1  |                 .> celery           exchange=celery(direct) key=celery
celery-worker-1  |                 
celery-worker-1  | 
celery-worker-1  | [tasks]
celery-worker-1  | 
celery-worker-1  | 
elom@elom-Latitude-E7470:~/Schreibtisch/SaaS_Web_Application_digitale_presenz/backend$ docker compose logs --tail=100 celery-beat
celery-beat-1  | celery beat v5.5.3 (immunity) is starting.
celery-beat-1  | __    -    ... __   -        _
celery-beat-1  | LocalTime -> 2026-08-22 09:18:46
celery-beat-1  | Configuration ->
celery-beat-1  |     . broker -> redis://redis:6379/1
celery-beat-1  |     . loader -> celery.loaders.app.AppLoader
celery-beat-1  |     . scheduler -> celery.beat.PersistentScheduler
celery-beat-1  |     . db -> celerybeat-schedule
celery-beat-1  |     . logfile -> [stderr]@%INFO
celery-beat-1  |     . maxinterval -> 5.00 minutes (300s)
elom@elom-Latitude-E7470:~/Schreibtisch/SaaS_Web_Application_digitale_presenz/backend$ docker compose ps
NAME                      IMAGE                   COMMAND                  SERVICE         CREATED         STATUS                   PORTS
backend-celery-beat-1     backend-celery-beat     "celery -A config be…"   celery-beat     7 minutes ago   Up 6 minutes             8000/tcp
backend-celery-worker-1   backend-celery-worker   "celery -A config wo…"   celery-worker   7 minutes ago   Up 6 minutes             8000/tcp
backend-db-1              postgres:16-alpine      "docker-entrypoint.s…"   db              7 minutes ago   Up 7 minutes (healthy)   5432/tcp
backend-nginx-1           nginx:1.27-alpine       "/docker-entrypoint.…"   nginx           7 minutes ago   Up 6 minutes (healthy)   0.0.0.0:8080->80/tcp, [::]:8080->80/tcp
backend-redis-1           redis:7-alpine          "docker-entrypoint.s…"   redis           7 minutes ago   Up 7 minutes (healthy)   6379/tcp
backend-web-1             backend-web             "sh -c 'python manag…"   web             7 minutes ago   Up 6 minutes (healthy)   8000/tcp
elom@elom-Latitude-E7470:~/Schreibtisch/SaaS_Web_Application_digitale_presenz/backend$ 

