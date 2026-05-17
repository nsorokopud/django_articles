from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0006_alter_profile_image"),
        ("account", "0009_emailaddress_unique_primary_email"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE UNIQUE INDEX
                    account_emailaddress_email_ci_unique
                ON account_emailaddress (LOWER(TRIM(email)));
            """,
            reverse_sql="""
                DROP INDEX IF EXISTS account_emailaddress_email_ci_unique;
            """,
        ),
        migrations.RunSQL(
            sql="""
                CREATE UNIQUE INDEX
                    account_one_non_primary_email_per_user
                ON account_emailaddress (user_id)
                WHERE "primary" IS FALSE;
            """,
            reverse_sql="""
                DROP INDEX IF EXISTS account_one_non_primary_email_per_user;
            """,
        ),
    ]
