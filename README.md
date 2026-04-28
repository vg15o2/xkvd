# xkvd

xkcd-style stick-figure comics, auto-generated from my Letterboxd reviews.

## How it works

1. A Python script fetches `https://letterboxd.com/<user>/rss/`.
2. For every entry that has actual review text, it generates a stick-figure SVG comic with speech bubbles taken from the review, plus an alt-text line that shows on hover.
3. Each comic becomes a Jekyll document under `_comics/`; the SVG goes in `assets/comics/`.
4. Jekyll builds the site (xkcd-style header with Prev / Random / Next / Latest / Archive).
5. A daily GitHub Action re-runs the script and commits any new strips.

## Local development

```sh
# generate comics from the Letterboxd feed
python scripts/build_comics.py

# build the site
bundle install
bundle exec jekyll serve
```

## Configuration

`_config.yml`:
- `letterboxd_username`: handle to fetch from `letterboxd.com/<handle>/rss/`.

## Deploy on Vercel

`vercel.json` is preconfigured with the Jekyll framework preset (`bundle exec jekyll build` → `_site`). Import the repo in Vercel and it should just work.
