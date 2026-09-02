from django.contrib import admin
from .models import SEOAudit, Keyword, Backlink

admin.site.register(SEOAudit)
admin.site.register(Keyword)
admin.site.register(Backlink)
