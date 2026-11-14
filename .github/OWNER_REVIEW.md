# Owner review checklist

Open items from the SEO/AEO/GEO work (PR #4, merged 2026-11-14). Tick each item once the owner has confirmed it.
This file lives in `.github/` so GitHub Pages does not publish it.

## Business facts to confirm
- [ ] **Saree draping:** price, available styles and any other details. None are published today; the site says details and prices are confirmed on WhatsApp.
- [ ] **Service areas for draping:** the site lists Tiruppur, Avinashi and Erode for both services. Confirm draping covers all three.
- [ ] **Logo:** is the DD monogram (`favicon.svg`) the official brand logo? Until confirmed, the Organization schema has no `logo`.
- [ ] **Pre-pleating style descriptions:** "Suited to everyday and office sarees" (box folding) and "Suited to functions and festivals" (semi-fluffy) came from the earlier site; confirm they are accurate.

## Claims removed from the site (re-add only if verified)
- [ ] Pickup, doorstep delivery and delivery routes
- [ ] Express / urgent preparation
- [ ] Family, bulk and business packages
- [ ] Silk and bridal saree handling
- [ ] "Appointments that suit you" and "On schedule, doorstep"
- [ ] "Personal care", "gentle with fabric", "even pleats, always"

`scripts/validate_seo.py` fails if wording from this list returns on an indexable page.

## Legal pages (noindex kept)
- [ ] `terms.html`: pickup/delivery/express and family/bulk wording removed, silk/bridal sentence removed, draping added. Review the wording.
- [ ] `privacy.html`: intro now mentions saree draping. Review the wording.

## Search Console (owner action)
- [ ] Inspect `/`, `/saree-pre-pleating/`, `/saree-draping/` and `/faq` in URL Inspection and review "Page indexing".
- [ ] Confirm `sitemap.xml` shows 4 discovered pages in the Sitemaps report.
- [ ] Decide whether to request indexing. This has not been done.

## Known limitations
- `/faq` and `/faq.html` both return 200 on GitHub Pages; the canonical tag points to `/faq`.
- The pre-pleating meta description is 213 characters (copy specified by the owner); search results may truncate it.
- Not tested: WhatsApp links opened live, external HTML validator, PageSpeed, rich-result eligibility, AI visibility.
- The homepage reports a scroll width wider than the viewport. This was already the case before the SEO work (marquee strip) and is not visible.
