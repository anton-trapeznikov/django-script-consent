import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


def seed_defaults(apps, schema_editor):
    ScriptCategory = apps.get_model("script_consent", "ScriptCategory")
    ScriptSnippet = apps.get_model("script_consent", "ScriptSnippet")
    BannerConfig = apps.get_model("script_consent", "BannerConfig")

    categories = [
        {
            "code": "technical",
            "title": "Essential",
            "description": (
                "Required for the website to work correctly: session, security, "
                "and consent preferences. They do not collect personal data and are not "
                "used to track users. These cannot be disabled."
            ),
            "is_required": True,
            "order": 0,
            "is_active": True,
        },
        {
            "code": "analytics",
            "title": "Analytics",
            "description": (
                "Help us understand how visitors use the site "
                "(for example, traffic counters). Used only with your consent."
            ),
            "is_required": False,
            "order": 10,
            "is_active": True,
        },
        {
            "code": "marketing",
            "title": "Marketing",
            "description": (
                "Used to show relevant ads and measure their effectiveness. "
                "Loaded only with your consent."
            ),
            "is_required": False,
            "order": 20,
            "is_active": True,
        },
    ]
    for data in categories:
        ScriptCategory.objects.update_or_create(code=data["code"], defaults=data)

    if not BannerConfig.objects.exists():
        BannerConfig.objects.create(
            title="We use cookies",
            text=(
                "This site uses cookies and similar technologies to run the service, "
                "for analytics, and (with your consent) for marketing. "
                "You may accept all categories, choose specific ones, or keep only "
                "essential cookies. See our privacy policy for details. "
                "Consent is specific to the set of active scripts at the time you agree; "
                "if that set changes, we will ask again."
            ),
            version=1,
            is_active=True,
        )

    snippets = [
        {
            "name": "Demo · Essential",
            "category_code": "technical",
            "placement": "head",
            "code": (
                "<script>"
                'console.log("[script-consent] essential / technical loaded");'
                "</script>"
            ),
            "always_load": False,
            "order": 0,
            "is_active": True,
        },
        {
            "name": "Demo · Analytics",
            "category_code": "analytics",
            "placement": "body_end",
            "code": (
                "<script>"
                'console.log("[script-consent] analytics loaded (consent required)");'
                "</script>"
            ),
            "always_load": False,
            "order": 10,
            "is_active": True,
        },
        {
            "name": "Demo · Marketing",
            "category_code": "marketing",
            "placement": "body_end",
            "code": (
                "<script>"
                'console.log("[script-consent] marketing loaded (consent required)");'
                "</script>"
            ),
            "always_load": False,
            "order": 20,
            "is_active": True,
        },
    ]
    for data in snippets:
        cat = ScriptCategory.objects.filter(code=data["category_code"]).first()
        if cat is None:
            continue
        ScriptSnippet.objects.update_or_create(
            name=data["name"],
            defaults={
                "category": cat,
                "placement": data["placement"],
                "code": data["code"],
                "always_load": data["always_load"],
                "order": data["order"],
                "is_active": data["is_active"],
            },
        )


def unseed_defaults(apps, schema_editor):
    ScriptCategory = apps.get_model("script_consent", "ScriptCategory")
    ScriptSnippet = apps.get_model("script_consent", "ScriptSnippet")
    BannerConfig = apps.get_model("script_consent", "BannerConfig")
    ScriptSnippet.objects.filter(
        name__in=["Demo · Essential", "Demo · Analytics", "Demo · Marketing"]
    ).delete()
    ScriptCategory.objects.filter(
        code__in=["technical", "analytics", "marketing"]
    ).delete()
    BannerConfig.objects.all().delete()


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BannerConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255, verbose_name='Title')),
                ('text', models.TextField(help_text='Simple HTML is allowed', verbose_name='Text')),
                ('version', models.PositiveIntegerField(default=1, verbose_name='Version')),
                ('is_active', models.BooleanField(default=True, verbose_name='Active')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated')),
            ],
            options={
                'verbose_name': 'Banner configuration',
                'verbose_name_plural': 'Banner configurations',
                'ordering': ['-is_active', '-updated_at'],
            },
        ),
        migrations.CreateModel(
            name='RuntimeCacheStamp',
            fields=[
                ('key', models.PositiveSmallIntegerField(default=1, editable=False, primary_key=True, serialize=False)),
                ('generation', models.PositiveIntegerField(default=0)),
            ],
            options={
                'verbose_name': 'Runtime cache stamp',
                'verbose_name_plural': 'Runtime cache stamps',
            },
        ),
        migrations.CreateModel(
            name='ScriptCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.SlugField(max_length=64, unique=True, verbose_name='Code')),
                ('title', models.CharField(max_length=255, verbose_name='Title')),
                ('description', models.TextField(blank=True, verbose_name='Description')),
                ('is_required', models.BooleanField(default=False, help_text='Essential scripts: cannot be refused', verbose_name='Required')),
                ('order', models.PositiveIntegerField(default=0, verbose_name='Order')),
                ('is_active', models.BooleanField(default=True, verbose_name='Active')),
            ],
            options={
                'verbose_name': 'Script category',
                'verbose_name_plural': 'Script categories',
                'ordering': ['order', 'id'],
            },
        ),
        migrations.CreateModel(
            name='ConsentRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('consent_id', models.UUIDField(db_index=True, default=uuid.uuid4, verbose_name='Consent ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created')),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True, verbose_name='IP')),
                ('user_agent', models.TextField(blank=True, verbose_name='User-Agent')),
                ('action', models.CharField(choices=[('accept_all', 'Accept all'), ('reject_optional', 'Necessary only'), ('custom', 'Custom selection'), ('withdraw', 'Withdraw')], max_length=32, verbose_name='Action')),
                ('banner_version', models.PositiveIntegerField(verbose_name='Banner version')),
                ('scripts_hash', models.CharField(max_length=64, verbose_name='Scripts hash')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='script_consents', to=settings.AUTH_USER_MODEL, verbose_name='User')),
                ('accepted_categories', models.ManyToManyField(blank=True, related_name='consent_records', to='script_consent.scriptcategory', verbose_name='Accepted categories')),
            ],
            options={
                'verbose_name': 'Consent record',
                'verbose_name_plural': 'Consent records',
                'ordering': ['-created_at'],
                'indexes': [models.Index(fields=['created_at'], name='script_cons_created_8116c9_idx'), models.Index(fields=['action'], name='script_cons_action_a19838_idx')],
            },
        ),
        migrations.CreateModel(
            name='ScriptSnippet',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='Name')),
                ('placement', models.CharField(choices=[('head', 'Head'), ('body_start', 'Body start'), ('body_end', 'Body end')], default='body_end', max_length=16, verbose_name='Placement')),
                ('code', models.TextField(help_text='HTML/JS code', verbose_name='Snippet code')),
                ('always_load', models.BooleanField(default=False, help_text='If checked, the snippet is always loaded and does not participate in the consent prompt (regardless of category).', verbose_name='Load without consent')),
                ('is_active', models.BooleanField(default=True, verbose_name='Active')),
                ('order', models.PositiveIntegerField(default=0, verbose_name='Order')),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='scripts', to='script_consent.scriptcategory', verbose_name='Category')),
            ],
            options={
                'verbose_name': 'Script / snippet',
                'verbose_name_plural': 'Scripts / snippets',
                'ordering': ['order', 'id'],
                'indexes': [models.Index(fields=['is_active', 'placement', 'order'], name='script_cons_is_acti_19b7ac_idx')],
            },
        ),
        migrations.RunPython(seed_defaults, unseed_defaults),
    ]
