#!/bin/sh
# Local headless WordPress bootstrap.
#
# Runs once in the `wordpress-init` container after WordPress is healthy:
#   1. installs the site if the database is empty;
#   2. imports the six editorial articles from ./seed (only when no post exists).
#
# The container has no public port. Content is managed either through
# `docker compose exec wordpress wp ...` or the loopback-only admin on :8081.
set -eu

WP="wp --allow-root --path=/var/www/html"

# Ensure a term exists and return its id (name is the label, slug the code).
language_term() {
  lang="$1"
  term_id="$($WP term get language "$lang" --by=slug --field=term_id 2>/dev/null || true)"
  if [ -z "$term_id" ]; then
    term_id="$($WP term create language "$(printf '%s' "$lang" | tr '[:lower:]' '[:upper:]')" --slug="$lang" --porcelain)"
  fi
  printf '%s' "$term_id"
}


echo "[wordpress-init] waiting for WordPress core files…"
i=0
until [ -f /var/www/html/wp-config.php ]; do
  i=$((i + 1))
  if [ "$i" -gt 60 ]; then
    echo "[wordpress-init] timed out waiting for wp-config.php" >&2
    exit 1
  fi
  sleep 2
done

if ! $WP core is-installed 2>/dev/null; then
  echo "[wordpress-init] installing WordPress at ${WORDPRESS_URL:-http://localhost/cms}"
  $WP core install \
    --url="${WORDPRESS_URL:-http://localhost/cms}" \
    --title="${WORDPRESS_TITLE:-Presence Blog}" \
    --admin_user="${WORDPRESS_ADMIN_USER:-presence-admin}" \
    --admin_email="${WORDPRESS_ADMIN_EMAIL:-admin@presence.local}" \
    --admin_password="${WORDPRESS_ADMIN_PASSWORD:-local-admin-only}" \
    --skip-email
else
  echo "[wordpress-init] WordPress already installed"
fi

if [ -f /var/www/html/wp-content/mu-plugins/presence-i18n.php ]; then
  echo "[wordpress-init] language layer present"
else
  echo "[wordpress-init] WARNING: presence-i18n.php is not mounted — blog stays monolingual" >&2
fi

existing="$($WP post list --post_type=post --post_status=publish --format=count)"
if [ "$existing" = "1" ] && [ "$($WP post list --post_type=post --post_status=publish --field=post_name)" = "hello-world" ]; then
  echo "[wordpress-init] removing the default WordPress sample post"
  $WP post delete "$($WP post list --post_type=post --post_status=publish --format=ids)" --force >/dev/null
  existing="0"
fi
# The language tagging and the German articles below stay idempotent and must
# still run when the English seed is already in place, so this block only skips
# the English import itself.
if [ "$existing" != "0" ]; then
  echo "[wordpress-init] $existing published post(s) already present — English seed skipped"
  seed_english=0
else
  seed_english=1
fi

if [ "$seed_english" = "1" ]; then
echo "[wordpress-init] seeding editorial articles"
# TSV: slug|category|post_date|title|excerpt
while IFS='|' read -r slug category post_date title excerpt; do
  [ -z "$slug" ] && continue
  category_slug="$(printf '%s' "$category" | tr '[:upper:] ' '[:lower:]-')"
  term_id="$($WP term get category "$category_slug" --by=slug --field=term_id 2>/dev/null || true)"
  if [ -z "$term_id" ]; then
    term_id="$($WP term create category "$category" --slug="$category_slug" --porcelain)"
  fi
  created="$($WP post create "/seed/$slug.html" \
    --post_type=post \
    --post_status=publish \
    --post_title="$title" \
    --post_name="$slug" \
    --post_excerpt="$excerpt" \
    --post_date="$post_date" \
    --post_category="$term_id" \
    --porcelain \
    --allow-root)"
  # English originals are tagged `en` so the frontend can request one language.
  $WP post term set "$created" language en >/dev/null 2>&1 || true
done < /seed/00-index.tsv
fi

# German articles: translated content linked back to its English original.
if [ -f /seed/de-index.tsv ]; then
  de_created=0
  while IFS='|' read -r slug category post_date title excerpt source_slug; do
    [ -z "$slug" ] && continue
    source_id="$($WP post list --post_type=post --name="$source_slug" --field=ID --format=ids 2>/dev/null | head -n1)"
    existing_de="$($WP post list --post_type=post --name="$slug" --post_status=any --field=ID --format=ids 2>/dev/null | head -n1)"
    if [ -n "$existing_de" ]; then
      # Idempotent: re-assert the language and the translation link.
      $WP post term set "$existing_de" language de >/dev/null 2>&1 || true
      if [ -n "$source_id" ]; then
        $WP post meta update "$existing_de" _presence_translation_of "$source_id" >/dev/null 2>&1 || true
      fi
      continue
    fi
    category_slug="$(printf '%s' "$category" | tr '[:upper:] ' '[:lower:]-')"
    term_id="$($WP term get category "$category_slug" --by=slug --field=term_id 2>/dev/null || true)"
    if [ -z "$term_id" ]; then
      term_id="$($WP term create category "$category" --slug="$category_slug" --porcelain)"
    fi
    created="$($WP post create "/seed/$slug.html" \
      --post_type=post \
      --post_status=publish \
      --post_title="$title" \
      --post_name="$slug" \
      --post_excerpt="$excerpt" \
      --post_date="$post_date" \
      --post_category="$term_id" \
      --porcelain \
      --allow-root)"
    $WP post term set "$created" language de >/dev/null 2>&1 || true
    if [ -n "$source_id" ]; then
      $WP post meta update "$created" _presence_translation_of "$source_id" >/dev/null 2>&1 || true
    fi
    de_created=$((de_created + 1))
  done < /seed/de-index.tsv
  echo "[wordpress-init] German articles created: $de_created"
fi

# Existing English posts that predate the language layer get tagged too.
if [ -f /var/www/html/wp-content/mu-plugins/presence-i18n.php ]; then
  for id in $($WP post list --post_type=post --post_status=publish --format=ids); do
    # `--field=slug --format=csv` prints nothing when no term is assigned, so an
    # empty answer is the reliable "no language yet" signal. Asking for `ids`
    # while requesting a field always printed nothing and re-tagged every post.
    assigned="$($WP post term list "$id" language --field=slug --format=csv 2>/dev/null | tr -d '[:space:]')"
    if [ -z "$assigned" ]; then
      $WP post term set "$id" language en >/dev/null 2>&1 || true
    fi
  done
fi

$WP rewrite structure '/%postname%/' --hard >/dev/null 2>&1 || true
echo "[wordpress-init] done"
