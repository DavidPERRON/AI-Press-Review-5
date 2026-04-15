from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from xml.sax.saxutils import escape

from ..models import PublishedEpisode
from ..settings import DOCS_DIR, load_settings
from ..state import load_episode_history, save_episode_history
from ..storage.r2 import delete_key
from ..utils import utcnow


def publish_episode(
    episode: PublishedEpisode,
    source_fingerprints: list[str],
    source_titles: list[str],
    *,
    script: str | None = None,
    key_claims: list[dict] | None = None,
    grounding_report: dict | None = None,
) -> None:
    history = load_episode_history()
    episodes = history.get('episodes', [])
    payload = episode.to_dict()
    payload['source_fingerprints'] = source_fingerprints
    payload['source_titles'] = source_titles
    if script is not None:
        payload['script'] = script
    if key_claims is not None:
        payload['key_claims'] = key_claims
    if grounding_report is not None:
        payload['grounding_report'] = grounding_report
    payload['source_count'] = len(source_fingerprints)
    payload['domain_count'] = _count_domains(source_titles)
    episodes.insert(0, payload)

    settings = load_settings()
    cutoff = utcnow() - timedelta(days=settings.retention_days)

    kept = []
    for item in episodes:
        published_at = datetime.fromisoformat(item['published_at'])
        if published_at >= cutoff:
            kept.append(item)
        else:
            try:
                key = item['audio_url'].replace(settings.public_audio_base_url.rstrip('/') + '/', '')
                delete_key(key)
            except Exception:
                pass
            # Remove stale per-episode transcript pages as well.
            _remove_episode_artifacts(item.get('slug', ''))

    history['episodes'] = kept
    save_episode_history(history)
    _write_transcripts(kept)
    _write_feed(kept)
    _write_index(kept)
    _write_sitemap(kept)
    _write_robots()


def _count_domains(source_titles: list[str]) -> int:
    """Best-effort domain count — if only titles are available, we can't
    compute it exactly, so we leave this as a placeholder the pipeline
    may override later."""
    return 0


def _remove_episode_artifacts(slug: str) -> None:
    if not slug:
        return
    episode_dir = DOCS_DIR / 'episodes' / slug
    if episode_dir.exists():
        for child in episode_dir.iterdir():
            try:
                child.unlink()
            except Exception:
                pass
        try:
            episode_dir.rmdir()
        except Exception:
            pass


def _write_transcripts(episodes: list[dict]) -> None:
    """Regenerate per-episode transcript artifacts (VTT + HTML) for
    every retained episode. Cheap enough at our scale (≤10 episodes)."""
    from .transcript import write_transcript_artifacts

    settings = load_settings()
    for ep in episodes:
        script = ep.get('script') or ''
        if not script:
            continue
        try:
            urls = write_transcript_artifacts(
                docs_dir=DOCS_DIR,
                slug=ep['slug'],
                script=script,
                duration_seconds=int(ep.get('duration_seconds') or 0),
                episode_meta={
                    'title': ep['title'],
                    'summary': ep.get('summary', ''),
                    'published_at': ep.get('published_at', ''),
                    'audio_url': ep.get('audio_url', ''),
                },
                site_base_url=_base_url(settings),
                feed_url=_feed_url(settings),
                cover_url=_absolute(settings, settings.cover_image_path),
                author=settings.podcast_author,
                language=settings.podcast_language,
                key_claims=ep.get('key_claims') or [],
                grounding_coverage=(ep.get('grounding_report') or {}).get('coverage_ratio'),
                source_count=ep.get('source_count', 0),
                domain_count=ep.get('domain_count', 0),
            )
            ep['transcript_vtt_url'] = urls['vtt_url']
            ep['episode_page_url'] = urls['html_url']
        except Exception:
            # Transcript generation is best-effort — never block publish.
            pass


# ── helpers ──────────────────────────────────────────────────────────────────

def _base_url(settings) -> str:
    return settings.site_base_url.rstrip('/')


def _absolute(settings, path: str) -> str:
    if path.startswith('http://') or path.startswith('https://'):
        return path
    return f"{_base_url(settings)}/{path.lstrip('/')}"


def _feed_url(settings) -> str:
    return settings.rss_feed_url or f"{_base_url(settings)}/podcast-feed.xml"


def _secondary_category_xml(settings) -> str:
    if not settings.category_secondary:
        return ''
    if settings.category_secondary.strip().lower() == 'artificial intelligence':
        return '<itunes:category text="Technology"><itunes:category text="Artificial Intelligence" /></itunes:category>'
    return f'<itunes:category text="{escape(settings.category_secondary)}" />'


# ── RSS feed ─────────────────────────────────────────────────────────────────

_PODCAST_NS = 'https://podcastindex.org/namespace/1.0'


def _channel_guid(settings) -> str:
    """Stable channel GUID per Podcasting 2.0 spec. Deterministic UUIDv5
    derived from the podcast feed URL so it stays identical across
    regenerations but changes if the operator forks/moves the feed."""
    import uuid
    return str(uuid.uuid5(uuid.NAMESPACE_URL, _feed_url(settings)))


def _podcast_person_xml(settings) -> str:
    return (
        f'<podcast:person role="host" group="cast">'
        f'{escape(settings.podcast_author)}'
        '</podcast:person>'
    )


def _write_feed(episodes: list[dict]) -> None:
    settings = load_settings()
    feed_url = _feed_url(settings)
    cover_url = _absolute(settings, settings.cover_image_path)
    description = settings.podcast_description_long or settings.podcast_description_short
    last_build = format_datetime(utcnow())

    items = []
    for ep in episodes:
        pub_date = format_datetime(datetime.fromisoformat(ep['published_at']))
        transcript_tag = ''
        if ep.get('transcript_vtt_url'):
            transcript_tag = (
                f'<podcast:transcript url="{escape(ep["transcript_vtt_url"])}" '
                f'type="text/vtt" rel="captions" />'
            )
        episode_page = ep.get('episode_page_url') or ep.get('source_manifest_url')
        duration_tag = ''
        if ep.get('duration_seconds'):
            duration_tag = f'<itunes:duration>{int(ep["duration_seconds"])}</itunes:duration>'
        items.append(
            f"<item><title>{escape(ep['title'])}</title>"
            f"<description>{escape(ep['summary'])}</description>"
            f"<guid isPermaLink=\"false\">{escape(ep['audio_url'])}</guid>"
            f"<pubDate>{pub_date}</pubDate>"
            f'<enclosure url="{escape(ep["audio_url"])}" length="{ep["audio_bytes"]}" type="audio/mpeg" />'
            f"<itunes:summary>{escape(ep['summary'])}</itunes:summary>"
            f'<itunes:image href="{escape(cover_url)}" />'
            f"<itunes:explicit>{'true' if settings.explicit else 'false'}</itunes:explicit>"
            f"{duration_tag}"
            f"{transcript_tag}"
            f"{_podcast_person_xml(settings)}"
            f"<link>{escape(episode_page)}</link></item>"
        )

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0" '
        'xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" '
        'xmlns:content="http://purl.org/rss/1.0/modules/content/" '
        'xmlns:atom="http://www.w3.org/2005/Atom" '
        f'xmlns:podcast="{_PODCAST_NS}">'
        '<channel>'
        f"<title>{escape(settings.podcast_title)}</title>"
        f"<link>{escape(_base_url(settings))}</link>"
        f'<atom:link href="{escape(feed_url)}" rel="self" type="application/rss+xml" />'
        f"<language>{escape(settings.podcast_language)}</language>"
        f"<lastBuildDate>{last_build}</lastBuildDate>"
        '<generator>ai-press-review</generator>'
        # Podcasting 2.0 channel-level
        f'<podcast:guid>{_channel_guid(settings)}</podcast:guid>'
        '<podcast:medium>podcast</podcast:medium>'
        '<podcast:locked>no</podcast:locked>'
        f'{_podcast_person_xml(settings)}'
        f"<itunes:author>{escape(settings.podcast_author)}</itunes:author>"
        f"<itunes:subtitle>{escape(settings.podcast_subtitle)}</itunes:subtitle>"
        f"<itunes:summary>{escape(settings.podcast_description_short)}</itunes:summary>"
        f"<description>{escape(description)}</description>"
        '<itunes:type>episodic</itunes:type>'
        f"<itunes:explicit>{'true' if settings.explicit else 'false'}</itunes:explicit>"
        '<itunes:owner>'
        f"<itunes:name>{escape(settings.podcast_author)}</itunes:name>"
        f"<itunes:email>{escape(settings.podcast_email)}</itunes:email>"
        '</itunes:owner>'
        f'<itunes:image href="{escape(cover_url)}" />'
        f'<image><url>{escape(cover_url)}</url>'
        f"<title>{escape(settings.podcast_title)}</title>"
        f"<link>{escape(_base_url(settings))}</link></image>"
        f'<itunes:category text="{escape(settings.category_primary)}" />'
        f'{_secondary_category_xml(settings)}'
        f"{''.join(items)}"
        '</channel></rss>'
    )
    (DOCS_DIR / 'podcast-feed.xml').write_text(xml, encoding='utf-8')


# ── HTML landing page ────────────────────────────────────────────────────────

def _json_ld(settings, episodes: list[dict]) -> str:
    base = _base_url(settings)
    cover_url = _absolute(settings, settings.cover_image_path)
    description = settings.podcast_description_long or settings.podcast_description_short

    episode_nodes = []
    for ep in episodes[:10]:
        episode_nodes.append({
            '@type': 'PodcastEpisode',
            'name': ep['title'],
            'description': ep['summary'],
            'datePublished': ep['published_at'],
            'url': ep['audio_url'],
            'associatedMedia': {
                '@type': 'MediaObject',
                'contentUrl': ep['audio_url'],
                'encodingFormat': 'audio/mpeg',
            },
        })

    data = {
        '@context': 'https://schema.org',
        '@type': 'PodcastSeries',
        'name': settings.podcast_title,
        'url': base,
        'description': description,
        'image': cover_url,
        'inLanguage': settings.podcast_language,
        'author': {'@type': 'Person', 'name': settings.podcast_author},
        'webFeed': _feed_url(settings),
    }
    if episode_nodes:
        data['episode'] = episode_nodes

    return json.dumps(data, ensure_ascii=False)


def _subscribe_buttons_html(settings, feed_url: str) -> str:
    """Inline subscribe links. RSS always shown; other platforms hidden
    until the operator adds a URL in config/podcast.yaml."""
    parts: list[str] = []
    if settings.apple_podcasts_url:
        parts.append(f"<a href='{escape(settings.apple_podcasts_url)}' rel='noopener' target='_blank'>Apple Podcasts</a>")
    if settings.spotify_url:
        parts.append(f"<a href='{escape(settings.spotify_url)}' rel='noopener' target='_blank'>Spotify</a>")
    if settings.youtube_url:
        parts.append(f"<a href='{escape(settings.youtube_url)}' rel='noopener' target='_blank'>YouTube</a>")
    parts.append(f"<a href='{escape(feed_url)}'>RSS</a>")
    return "<span class='dot'>&middot;</span>".join(parts)


def _arch_bars_svg(n: int = 30, width: int = 320, baseline: int = 78,
                   max_h: int = 70, min_h: int = 8) -> str:
    """Render the waveform-arch SVG used inside the banner. Bars get
    progressively taller toward the center then back down, evoking a
    podcast waveform shaped as an arch."""
    bars = []
    center = (n - 1) / 2
    for i in range(n):
        normalized = abs(i - center) / center
        height = min_h + (max_h - min_h) * (1 - normalized ** 1.4)
        x = (i + 0.5) * (width / n)
        y_top = baseline - height
        bars.append(f'<line x1="{x:.1f}" y1="{baseline}" x2="{x:.1f}" y2="{y_top:.1f}" />')
    return (
        f'<svg class="banner-arch" viewBox="0 0 {width} {baseline + 4}" '
        'aria-hidden="true" role="presentation">'
        '<g stroke="#BF8520" stroke-width="2.4" stroke-linecap="round" fill="none">'
        f'{"".join(bars)}'
        '</g>'
        '</svg>'
    )


def _episode_card(ep: dict, base: str) -> str:
    episode_link = ep.get('episode_page_url') or f"{base}/episodes/{ep.get('slug', '')}/"
    pub_label = (ep.get('published_at') or '')[:10]
    duration = ''
    if ep.get('duration_seconds'):
        duration = f" &nbsp;&middot;&nbsp; {int(ep['duration_seconds']) // 60} min"
    return (
        f"<article class='card'>"
        f"<p class='card-meta'>{escape(pub_label)}{duration}</p>"
        f"<h3><a href='{escape(episode_link)}'>{escape(ep['title'])}</a></h3>"
        f"<p class='card-summary'>{escape(ep['summary'])}</p>"
        f"<p class='card-links'>"
        f"<a href='{escape(episode_link)}'>Transcript &amp; episode page</a> "
        f"<span class='dot'>&middot;</span> "
        f"<a href='{escape(ep['audio_url'])}'>Listen</a> "
        f"<span class='dot'>&middot;</span> "
        f"<a href='{escape(ep['source_manifest_url'])}'>Sources</a>"
        f"</p>"
        f"</article>"
    )


def _write_index(episodes: list[dict]) -> None:
    settings = load_settings()
    base = _base_url(settings)
    cover_rel = settings.cover_image_path
    cover_url = _absolute(settings, cover_rel)
    description = settings.podcast_description_short or settings.podcast_description_long
    feed_url = _feed_url(settings)

    keywords = (
        'AI podcast, artificial intelligence, generative AI, LLM, '
        'AI news, AI research, AI use cases, AI tools, weak signals, '
        'AI for business, daily AI briefing'
    )

    cards = [_episode_card(ep, base) for ep in episodes]
    empty = (
        "<div class='card empty'>"
        "<p class='card-meta'>Coming soon</p>"
        "<h3>First episode publishing within days.</h3>"
        "<p class='card-summary'>Subscribe via Apple, Spotify, YouTube, or RSS to be notified.</p>"
        "</div>"
    )
    subscribe_html = _subscribe_buttons_html(settings, feed_url)
    banner_svg = _arch_bars_svg()

    json_ld = _json_ld(settings, episodes)

    html = (
        "<!doctype html>"
        f"<html lang='{escape(settings.podcast_language)}'>"
        "<head>"
        "<meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{escape(settings.podcast_title)} &mdash; {escape(settings.podcast_subtitle)}</title>"
        f"<meta name='description' content='{escape(description)}'>"
        f"<meta name='keywords' content='{escape(keywords)}'>"
        f"<meta name='author' content='{escape(settings.podcast_author)}'>"
        "<meta name='robots' content='index,follow,max-image-preview:large'>"
        "<meta name='theme-color' content='#071028'>"
        f"<link rel='canonical' href='{escape(base)}/'>"
        f"<link rel='alternate' type='application/rss+xml' title='{escape(settings.podcast_title)} RSS' href='{escape(feed_url)}'>"
        f"<link rel='icon' type='image/png' href='{escape(cover_rel)}'>"
        f"<link rel='apple-touch-icon' href='{escape(cover_rel)}'>"
        # Open Graph
        "<meta property='og:type' content='website'>"
        f"<meta property='og:site_name' content='{escape(settings.podcast_title)}'>"
        f"<meta property='og:title' content='{escape(settings.podcast_title)} &mdash; {escape(settings.podcast_subtitle)}'>"
        f"<meta property='og:description' content='{escape(description)}'>"
        f"<meta property='og:url' content='{escape(base)}/'>"
        f"<meta property='og:image' content='{escape(cover_url)}'>"
        "<meta property='og:image:alt' content='AI Press Review cover'>"
        f"<meta property='og:locale' content='{escape(settings.podcast_language)}'>"
        # Twitter
        "<meta name='twitter:card' content='summary_large_image'>"
        f"<meta name='twitter:title' content='{escape(settings.podcast_title)}'>"
        f"<meta name='twitter:description' content='{escape(description)}'>"
        f"<meta name='twitter:image' content='{escape(cover_url)}'>"
        # JSON-LD
        f"<script type='application/ld+json'>{json_ld}</script>"
        # Web font
        "<link rel='preconnect' href='https://fonts.googleapis.com'>"
        "<link rel='preconnect' href='https://fonts.gstatic.com' crossorigin>"
        "<link rel='stylesheet' href='https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,400;0,500;0,600;0,700;1,400&display=swap'>"
        "<style>"
        # Palette derived from MAISON D'ALVENOR spec
        ":root{"
        "--bg:#FAF7F1;"
        "--bg-card:#FFFCF6;"
        "--ink:#1A1806;"
        "--ink-soft:#4A3E28;"
        "--rule:#E5DCC5;"
        "--navy:#071028;"
        "--gold:#BF8520;"
        "--gold-dark:#6B3F08;"
        "--gold-antique:#A87530;"
        "}"
        "*{box-sizing:border-box}"
        "html,body{margin:0;padding:0}"
        "body{font-family:'EB Garamond','Garamond','Cormorant Garamond',Georgia,serif;"
        "background:var(--bg);color:var(--ink);line-height:1.6;"
        "font-size:18px;-webkit-font-smoothing:antialiased}"
        "a{color:var(--gold-dark);text-decoration:none;border-bottom:1px solid transparent;"
        "transition:border-color .15s,color .15s}"
        "a:hover{color:var(--gold);border-bottom-color:var(--gold)}"
        # ── BANNER ──
        ".banner{background:var(--navy);padding:3.2rem 1.25rem 2.6rem;text-align:center;"
        "position:relative;border-bottom:1px solid var(--gold);overflow:hidden}"
        ".banner::before{content:'';position:absolute;inset:0;pointer-events:none;"
        "background:radial-gradient(circle at 50% 60%,rgba(191,133,32,.10) 0%,rgba(191,133,32,0) 55%)}"
        ".banner::after{content:'';position:absolute;inset:0;pointer-events:none;"
        "background:repeating-radial-gradient(circle at 50% 110%,transparent 0,transparent 80px,"
        "rgba(191,133,32,.04) 81px,rgba(191,133,32,.04) 82px)}"
        ".banner-inner{position:relative;z-index:1;max-width:760px;margin:0 auto}"
        ".banner-arch{display:block;width:min(320px,55vw);height:auto;margin:0 auto 1.1rem;opacity:.95}"
        ".banner-title{font-family:'EB Garamond',Garamond,Georgia,serif;font-weight:700;"
        "font-variant:small-caps;letter-spacing:.32em;color:var(--gold);"
        "font-size:clamp(1.55rem,4vw,2.5rem);margin:0;padding-left:.32em;line-height:1.1}"
        ".banner-rule{width:90px;height:1px;background:var(--gold);border:0;"
        "margin:.85rem auto .55rem;opacity:.55}"
        ".banner-author{font-family:'EB Garamond',Garamond,Georgia,serif;font-variant:small-caps;"
        "letter-spacing:.32em;color:var(--gold);font-size:.78rem;margin:0;padding-left:.32em;opacity:.85}"
        # ── PAGE WRAP ──
        ".wrap{max-width:760px;margin:0 auto;padding:2rem 1.25rem 3rem}"
        ".tagline{font-family:'EB Garamond',serif;font-style:italic;font-size:1.18rem;"
        "color:var(--ink-soft);text-align:center;margin:0 0 .35rem;line-height:1.4}"
        ".tagline-note{font-size:.82rem;color:var(--ink-soft);text-align:center;margin:0 0 1.4rem;"
        "font-variant:small-caps;letter-spacing:.18em}"
        # Subscribe row
        ".subscribe{text-align:center;margin:0 0 .55rem;font-size:1rem;color:var(--ink-soft)}"
        ".subscribe .label{font-variant:small-caps;letter-spacing:.18em;font-size:.78rem;"
        "color:var(--gold-antique);margin-right:.45rem}"
        ".subscribe a{color:var(--navy);font-weight:500}"
        ".subscribe a:hover{color:var(--gold-dark)}"
        ".subscribe .dot{margin:0 .45rem;color:var(--gold-antique);opacity:.7}"
        ".hiw-link{text-align:center;margin:.4rem 0 1.6rem;font-size:.85rem;"
        "font-variant:small-caps;letter-spacing:.2em}"
        ".hiw-link a{color:var(--gold-dark)}"
        # Section divider
        ".sect-rule{display:block;width:60px;height:1px;background:var(--gold-antique);"
        "border:0;margin:2rem auto 1.4rem;opacity:.6}"
        ".sect-head{font-family:'EB Garamond',serif;font-weight:700;font-variant:small-caps;"
        "letter-spacing:.22em;color:var(--gold-dark);font-size:.92rem;text-align:center;"
        "margin:0 0 1.1rem}"
        # Episode cards
        ".card{background:var(--bg-card);border:1px solid var(--rule);border-radius:4px;"
        "padding:1.3rem 1.5rem;margin:0 0 1rem;transition:border-color .2s,box-shadow .2s}"
        ".card:hover{border-color:var(--gold-antique);box-shadow:0 4px 18px rgba(7,16,40,.05)}"
        ".card.empty{text-align:center;border-style:dashed}"
        ".card-meta{font-variant:small-caps;letter-spacing:.18em;font-size:.78rem;"
        "color:var(--gold-antique);margin:0 0 .35rem}"
        ".card h3{font-family:'EB Garamond',serif;font-weight:700;color:var(--navy);"
        "font-size:1.4rem;line-height:1.25;margin:0 0 .55rem}"
        ".card h3 a{color:var(--navy);border-bottom:none}"
        ".card h3 a:hover{color:var(--gold-dark);border-bottom:none}"
        ".card-summary{margin:0 0 .8rem;color:var(--ink);font-size:1rem;line-height:1.55}"
        ".card-links{margin:0;font-size:.88rem;color:var(--ink-soft)}"
        ".card-links a{color:var(--gold-dark)}"
        ".card-links .dot{margin:0 .25rem;color:var(--gold-antique);opacity:.7}"
        # How it works
        "#how-it-works{margin-top:3rem;padding-top:1.6rem;border-top:1px solid var(--rule)}"
        "#how-it-works h2{font-family:'EB Garamond',serif;font-weight:700;color:var(--navy);"
        "font-size:1.6rem;margin:0 0 .35rem;text-align:center}"
        "#how-it-works .lead{text-align:center;font-style:italic;color:var(--ink-soft);"
        "margin:.25rem 0 1.6rem;font-size:1rem}"
        ".hiw-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));"
        "gap:1rem;margin:0 auto}"
        ".hiw-step{padding:1.1rem 1.25rem;background:var(--bg-card);"
        "border:1px solid var(--rule);border-radius:4px}"
        ".hiw-step strong{display:block;font-family:'EB Garamond',serif;font-weight:700;"
        "color:var(--navy);font-size:1.05rem;margin-bottom:.3rem;letter-spacing:.01em}"
        ".hiw-step span{color:var(--ink-soft);font-size:.95rem;line-height:1.5}"
        # Footer
        "footer{margin-top:3rem;padding:1.4rem 1rem 1rem;border-top:1px solid var(--rule);"
        "text-align:center;color:var(--ink-soft);font-size:.85rem}"
        "footer .sep{margin:0 .5rem;color:var(--gold-antique);opacity:.7}"
        "footer a{color:var(--gold-dark)}"
        # Mobile tweaks
        "@media (max-width:560px){"
        ".banner{padding:2.4rem 1rem 1.9rem}"
        ".banner-title{font-size:1.4rem;letter-spacing:.28em}"
        ".banner-author{font-size:.7rem}"
        ".wrap{padding:1.5rem 1rem 2rem}"
        ".card{padding:1.1rem 1.15rem}"
        ".card h3{font-size:1.2rem}"
        "}"
        "</style>"
        "</head>"
        "<body>"
        # ── BANNER ──
        "<header class='banner'>"
        "<div class='banner-inner'>"
        f"{banner_svg}"
        f"<h1 class='banner-title'>{escape(settings.podcast_title)}</h1>"
        "<hr class='banner-rule' />"
        f"<p class='banner-author'>{escape(settings.podcast_author)}</p>"
        "</div>"
        "</header>"
        # ── PAGE ──
        "<div class='wrap'>"
        f"<p class='tagline'>{escape(settings.podcast_subtitle)}</p>"
        "<p class='tagline-note'>An editorial podcast &middot; Daily, 7&thinsp;AM CET</p>"
        f"<p class='subscribe'><span class='label'>Subscribe</span>{subscribe_html}</p>"
        "<p class='hiw-link'><a href='#how-it-works'>How it works &rarr;</a></p>"
        # ── EPISODES ──
        "<hr class='sect-rule' />"
        "<h2 class='sect-head'>Latest episodes</h2>"
        "<main>"
        f"{''.join(cards) if cards else empty}"
        "</main>"
        # ── HOW IT WORKS ──
        "<section id='how-it-works'>"
        "<h2>How it works</h2>"
        f"<p class='lead'>{escape(description)}</p>"
        "<div class='hiw-grid'>"
        "<div class='hiw-step'><strong>40+ sources, weighted</strong>"
        "<span>A minimum threshold &mdash; not a target. Primary labs (OpenAI, DeepMind, Anthropic, arXiv) carry more weight than aggregators. Regulatory speculation and unverified rumors are excluded.</span></div>"
        "<div class='hiw-step'><strong>Semantic clustering</strong>"
        "<span>Sources reporting the same story are grouped before the editorial pass. Single-source claims are flagged as weak signals rather than amplified as news.</span></div>"
        "<div class='hiw-step'><strong>Claim &rarr; source grounding</strong>"
        "<span>Every factual claim in the script is verified against its cited source. Per-episode coverage is published on the transcript page.</span></div>"
        "<div class='hiw-step'><strong>14&ndash;18 minute briefing</strong>"
        "<span>Six pillars: AI News, Use Cases, Tools &amp; Practice, Weak Signals, Research, Education. Every Saturday, a weekly recap of the five trends that defined the week.</span></div>"
        "</div>"
        "</section>"
        "</div>"
        "<footer>"
        f"Hosted by {escape(settings.podcast_author)}"
        f"<span class='sep'>&middot;</span><a href='{escape(feed_url)}'>RSS feed</a>"
        "</footer>"
        "</body></html>"
    )
    (DOCS_DIR / 'index.html').write_text(html, encoding='utf-8')


# ── sitemap.xml & robots.txt ─────────────────────────────────────────────────

def _write_sitemap(episodes: list[dict]) -> None:
    settings = load_settings()
    base = _base_url(settings)
    feed_url = _feed_url(settings)

    if episodes:
        last_pub = max(ep['published_at'] for ep in episodes)
        lastmod = datetime.fromisoformat(last_pub).astimezone(timezone.utc).date().isoformat()
    else:
        lastmod = utcnow().date().isoformat()

    urls = [
        ('', 'daily', '1.0', lastmod),
        ('podcast-feed.xml', 'daily', '0.9', lastmod),
    ]
    # Per-episode transcript pages — indexable content is the real SEO lever.
    for ep in episodes:
        slug = ep.get('slug')
        if not slug:
            continue
        ep_date = (ep.get('published_at') or lastmod)[:10]
        urls.append((f'episodes/{slug}/', 'weekly', '0.8', ep_date))
    url_nodes = ''.join(
        f'<url><loc>{escape(base)}/{escape(path)}</loc>'
        f'<lastmod>{lastmod}</lastmod>'
        f'<changefreq>{freq}</changefreq>'
        f'<priority>{prio}</priority></url>'
        for path, freq, prio, lastmod in urls
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f'{url_nodes}'
        '</urlset>'
    )
    (DOCS_DIR / 'sitemap.xml').write_text(xml, encoding='utf-8')


def _write_robots() -> None:
    settings = load_settings()
    base = _base_url(settings)
    content = (
        "User-agent: *\n"
        "Allow: /\n"
        f"Sitemap: {base}/sitemap.xml\n"
    )
    (DOCS_DIR / 'robots.txt').write_text(content, encoding='utf-8')
