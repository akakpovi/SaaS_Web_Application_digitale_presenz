from django.contrib import admin
from .models import (
    ReviewSource,
    Review,
    ResponseDraft,
    ReviewSentiment,
    ReviewImportJob,
)

admin.site.register(ReviewSource)
admin.site.register(Review)
admin.site.register(ResponseDraft)
admin.site.register(ReviewSentiment)
admin.site.register(ReviewImportJob)
