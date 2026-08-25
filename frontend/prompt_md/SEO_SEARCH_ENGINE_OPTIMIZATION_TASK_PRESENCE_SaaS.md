                         INTERNET
                            │
                            ▼
                  ┌──────────────────┐
                  │ Cloudflare / CDN │
                  │ HTTPS / WAF      │
                  └────────┬─────────┘
                           │
              ┌────────────▼────────────┐
              │        Nginx            │
              │ Reverse Proxy / TLS     │
              └────────────┬────────────┘
                           │
            ┌──────────────▼──────────────┐
            │       Django REST API      │
            │                            │
            │ Authentication             │
            │ Websites                   │
            │ Scans                      │
            │ Monitoring                 │
            │ Alerts                     │
            │ Reports                    │
            │ Reviews                    │
            │ Billing                    │
            └───────┬───────────┬────────┘
                    │           │
          ┌─────────▼───┐   ┌──▼──────────┐
          │ PostgreSQL  │   │    Redis    │
          │             │   │ cache/broker│
          └─────────────┘   └──────┬──────┘
                                   │
                            ┌──────▼──────┐
                            │   Celery    │
                            │   Workers   │
                            └──────┬──────┘
                                   │
              ┌────────────────────┼───────────────────┐
              │                    │                   │
              ▼                    ▼                   ▼
        Website Scanner      DNS/SSL Scanner    Email Security
              │                    │                   │
              ├────────────────────┼───────────────────┤
              │                    │                   │
              ▼                    ▼                   ▼
       Security Headers       Performance          Uptime
