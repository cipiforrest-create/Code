# AJLA WEDDINGS — portfolio upgrade plan

Upgrade of https://ajla-weddings.vercel.app/ based on the client's voice notes
(2 videos from Ajla, plus 1 feedback video about dipstudio.ba) and two reference sites:
https://www.davidbastianoni.com/ and https://albertpalmerphotography.com/.

The working prototype for the hero animation is in [`hero-prototype.html`](./hero-prototype.html):
open it in a browser and use the A / B / C switch to show the client the three options.

---

## 1. What the client asked for (from the voice notes)

Ajla's own summary: *"hoću jednostavnu stranicu, koja će biti pristojna, fluidna, elegantna i to je to"*
(a simple page: decent, fluid, elegant). Everything below comes from her two recordings.

| # | Request (her words, paraphrased) | Where it goes |
|---|---|---|
| 1 | Brand name on top; when the page opens, something should happen ("da uskoči") | Hero: animated logo intro |
| 2 | Where the single big photo is, **10 of her chosen photos should rotate** and start moving on their own, at a calm pace, the moment people enter | Hero: rotating triptych (section 3) |
| 3 | Scrolling down: short text — based in BiH, available in Europe, editorial-vibe photographer | Intro block, 2–3 lines max |
| 4 | **"More about me"** button → her photo + a mini text | `/o-meni` / `/about` page |
| 5 | A strip of 2–3 photos, or the 10 in a smaller version, or **5 new photos that circulate** | Mid-page slow film-strip |
| 6 | **Portfolio** page with 40–50 of her photos; she will say which are for the portfolio and which for the home page | `/portfolio` gallery |
| 7 | **Reviews** — what clients said about her work, real ones (maybe some added later) | Testimonials section + optional page |
| 8 | Buttons to Portfolio and Contact at the end | Closing CTA |
| 9 | **Contact form**: name, surname, e-mail, month/date, **plus ready-made choices**: number of guests, wedding location, *what kind of couple are you* (love being photographed or not), anything else to add. Sent **to e-mail or WhatsApp — either is fine** | `/kontakt` |
| 10 | **Two languages**: Bosnian/Croatian first, English as the second, with a switch. If only one language is possible, English. | i18n across the whole site |
| 11 | Pretty fonts, **2 fonts, 3 max**, not too much text, everything nicely separated | Design system |
| 12 | Visual reference: the "Jennifer" template she screen-recorded (white, airy, small caps headings, side-by-side photos, slider arrows) and the AJLA demo on the laptop (three photos side by side, centre one in colour) | Overall look |

Assets still to come from Ajla: the 10 hero photos, the 40–50 portfolio photos (marked
home vs. portfolio), her portrait + short bio, real reviews, WhatsApp number.

### About the third video (dipstudio.ba)

The third recording is feedback on a **different site** (DIP Studio — special effects, lighting,
events in Sarajevo), not on Ajla's. It is not a list of Ajla's requirements, but it is the best
warning list we have for the animation, because it describes exactly what made that site feel broken:

- the hero video "stutters" and the page **blinks** ("vidiš kako mi blinka stranica")
- carousel items pass **too fast**, "hard to catch"
- duplicated labels, categories that overlap
- wants to **swipe with a finger** left/right, not only scroll down
- "*da se sad fokusiramo da stranica bude fluidna, pa ćemo se onda baviti tekstom*" — fluidity first, text later

Every rule in section 3 is there so Ajla's site does not get the same comments.

---

## 2. Audit of the current site

What is already good and should stay:
- Colour palette (`#F2EEE8` linen, `#20201F` ink, `#AD5E43` terracotta) and the pairing
  **Cormorant Garamond + Manrope** — already the 2-font system she asked for.
- Three-image hero with arrows, contact form with guests / location / planner fields,
  privacy consent, honeypot field, skip-link — solid foundation.

What has to change:
- **Visible placeholder text in production**: "Original editorial study — zamijeniti stvarnim
  radovima prije objave." must go before anything else.
- Hero is a manual slider of 3 photos → needs to be the automatic 10-photo rotation.
- **Too much text**: five numbered sections (01/05 … 05/05) with headings + paragraphs.
  She explicitly wants less. Cut to one line per section.
- No English version, no reviews, no portfolio page with 40–50 photos, no about page,
  no "type of couple" question, no WhatsApp option.
- Several photos are stock/illustrative ("Ilustrativna fotografija…") → replace with hers.

---

## 3. The rotating-photo animation — recommendation

She wants "something eye-catching" with her 10 chosen photos rotating. Three ways were
built and tested in the prototype:

| | A · Triptych **(recommended)** | B · Reveal | C · Marquee |
|---|---|---|---|
| What it does | 3 photos side by side; centre in colour, sides in black & white. Every ~5 s all three advance one step with a soft crossfade and a slow zoom-settle on the centre photo. | One large photo; the next one is revealed by an editorial "curtain" wipe from below. | An endless, slow film-strip of all photos drifting sideways. |
| Matches her brief | Exactly her sketch: "three on the side, where the one photo is, 10 rotate" — and the laptop demo she showed. | Good, but loses the 3-photo layout she pointed at. | Feels like Bastianoni's looping strips; better **mid-page** (request #5) than as the hero. |
| Feel | Calm, editorial, luxurious | Dramatic, fashion-magazine | Ambient |
| Risk | Low | Medium (wipes get tiring if too frequent) | Low |

**Recommendation: A for the hero, C for the "5 photos circulating" strip further down.**
That gives the page one striking moment at the top and one ambient moment in the middle,
without competing animations on the same screen. Plus a one-time **letter-by-letter logo
intro** for "AJLA WEDDINGS" — this is the "something should happen when it opens" she asked for.

### Rules that keep it fluid (lessons from the DIP Studio feedback)

1. **Never blink** — every photo is downloaded *and decoded* (`img.decode()`) before it is
   shown, and transitions are crossfades between two stacked layers, never a source swap
   on a visible image.
2. **Not too fast** — 5 s per photo, 1.4 s transition, side panels lag the centre by 180 ms
   so the motion reads as one calm wave.
3. **Swipe** left/right with a finger, arrows on desktop, keyboard ← →.
4. **Pause when the tab is hidden**, so returning never fast-forwards several photos.
5. **Only `opacity` and `transform` animate** (GPU-composited) — no layout jank.
6. **Image budget**: hero photos exported at 1600 px long edge, WebP/AVIF, ~150–250 KB each;
   first 3 loaded immediately, the other 7 after the page has loaded.
7. **`prefers-reduced-motion`**: no zoom, no auto-advance, simple fades only.
8. Counter `01 / 10` with `aria-live`, and the carousel is labelled for screen readers.

No library is needed for this: ~120 lines of vanilla JS + CSS (see prototype). For the
portfolio and reviews sliders, use **Embla Carousel** (tiny, swipe-native) if the site is React.

---

## 4. New site map

```
/                (BS)   /en                 (EN)
├── Hero            logo intro + rotating triptych (10 photos)
├── Intro           one line: editorial wedding photographer · Sarajevo · BiH & Europe
│                   [ Više o meni → ]
├── Film-strip      5 photos drifting slowly (or the 10 hero photos, smaller)
├── Reviews         3 short quotes, swipeable, [ Sve recenzije → ]
└── Closing CTA     one big photo + [ Portfolio ]  [ Kontakt ]

/portfolio  /en/portfolio      40–50 photos, masonry grid, lightbox with swipe
/o-meni     /en/about          her portrait + 4–6 sentences
/recenzije  /en/reviews        all reviews (optional — can stay a section only)
/kontakt    /en/contact        the enquiry form
/privatnost /en/privacy        existing privacy page, translated
```

Section text: **one heading + one sentence max** each. Remove the `01 / 05` numbering.

---

## 5. Page-by-page spec

### Home
- **Hero** — prototype variant A. Caption under it: one italic line
  ("Umjetnost, stil i iskrene emocije." / "Art, style and honest emotion.").
- **Intro** — 2 lines: based in Sarajevo, available across BiH and Europe, editorial vibe.
  Button "Više o meni" / "More about me".
- **Film-strip** — variant C with 5 photos she picks for the middle of the page.
- **Reviews** — 3 quotes, couple names + location, swipe. Inspired by Albert Palmer's
  short one-line quotes placed between photos (e.g. *"He fitted in to the day flawlessly."*).
- **Closing** — keep the existing first-dance closing image idea; two buttons only.

### Portfolio
- 40–50 photos, 2 columns mobile / 3 desktop, natural aspect ratios (masonry).
- Lazy-loaded, blur-up placeholders, lightbox with swipe and keyboard.
- Optional filter later (Ceremony / Portraits / Details / Party) — not in v1, keep simple.

### About (Više o meni)
- Her portrait (she said she will send it), 4–6 sentences, CTA to contact.

### Contact
Fields, in order:
1. Ime / First name *
2. Prezime / Last name *
3. E-mail *
4. Datum vjenčanja / Wedding date (month picker is enough) *
5. Lokacija vjenčanja / Wedding location *
6. Broj gostiju / Number of guests — chips: `do 50` · `50–100` · `100–200` · `200+`
7. **Kakav ste par? / What kind of couple are you?** — chips:
   `Volimo kameru` (love the camera) · `Malo smo stidljivi` (a bit shy) · `Nismo sigurni` (not sure yet)
8. Organizator vjenčanja (optional) — keep from current site
9. Nešto što bih trebala znati? / Anything else? (optional)
10. Privacy consent *

**Two send buttons** side by side:
- **Pošalji e-mail** — server action/API route sends the enquiry to `ajlaweddings@gmail.com`
  (Resend or Formspree; keep the existing honeypot).
- **Pošalji na WhatsApp** — opens `https://wa.me/<number>?text=…` with all answers pre-filled.
  No backend needed; works on phones instantly.

---

## 6. Languages

- Bosnian/Croatian is the default (`/`), English at `/en`. Toggle `BS | EN` in the header,
  stays on the same page when switched.
- If the site is Next.js: `next-intl` with two message files (`bs.json`, `en.json`).
  If it is static: two copies of the pages generated from one data file.
- `hreflang` tags + translated `<title>` and meta descriptions for both languages.
- The prototype already has the BS/EN switch wired for the hero text.

---

## 7. Design system

- **Fonts (2):** Cormorant Garamond (headings, logo, quotes) + Manrope (body, buttons, labels).
  No third font.
- **Colours:** keep the current linen / ink / terracotta palette; terracotta only for links
  and focus states.
- **Spacing:** generous; each section separated by whitespace, not by numbers or lines.
- **Buttons:** small uppercase Manrope with letter-spacing, thin border, square corners
  (matches the "Jennifer" reference she recorded).

---

## 8. Build order

| Phase | Work | Needs from Ajla |
|---|---|---|
| 1 | Remove placeholder note, cut text, new hero (variant A) with current photos, logo intro, fluidity rules | — |
| 2 | Contact form: new fields, "type of couple", WhatsApp + e-mail sending | WhatsApp number |
| 3 | BS / EN translations across all pages | Approve English copy |
| 4 | Portfolio page 40–50 photos + lightbox; film-strip section | Photo selection (home vs portfolio) |
| 5 | About page, reviews section/page | Portrait, bio, real reviews |
| 6 | QA: mobile (iPhone Safari + Android Chrome), Lighthouse ≥ 90, reduced-motion, slow 3G | — |

### Acceptance checks (to avoid DIP Studio–style feedback)
- [ ] Hero rotates by itself within 1 s of opening, no white flash between photos.
- [ ] On a mid-range phone the hero and the strip never stutter or blink.
- [ ] Swipe left/right works on every carousel.
- [ ] Every section has at most one heading and one sentence.
- [ ] BS/EN switch keeps you on the same page.
- [ ] Both send options deliver a complete enquiry.
- [ ] No placeholder or "illustrative photo" text left anywhere.

---

## 9. Open questions for Ajla

1. Variant A, B or C for the hero? (show her the prototype)
2. Should the side photos be black & white (as in the demo she showed) or in colour?
3. WhatsApp number for the contact button.
4. Reviews: is a section on the home page enough, or does she want a separate page?
5. Where is the current site's source code (GitHub repo / Vercel project)? — needed to apply
   these changes; it is not in this repository.
