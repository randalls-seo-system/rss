# Rank Logic Component Library

Visual reference for all rl-* components. Each section shows the class name, purpose, and HTML markup.

---

## rl-page

Root wrapper for all Rank Logic content. Provides the page-level scope, background gradient, and box-sizing reset.

```html
<section class="rl-page rl-page--{{slug}}" data-rl-page="{{slug}}">
  <!-- All rl-* content goes here -->
</section>
```

**Variants:** `rl-page--{{slug}}` for per-page targeting. Add `main-content` class for the BTF body section.

---

## rl-wrap

Centered content container. Max-width 1120px.

```html
<div class="rl-wrap">
  <!-- Content constrained to reading width -->
</div>
```

---

## rl-hero

The hero section at the top of an article. Contains breadcrumb, eyebrow, H1, sources, jump pills, lead paragraph, and CTA.

```html
<header class="rl-card rl-hero" aria-labelledby="article-title">
  <div class="rl-card-inner">
    <nav class="rl-breadcrumb" aria-label="Breadcrumb">
      <a href="/">Home</a>
      <span class="sep" aria-hidden="true">&rarr;</span>
      <a href="/category/">Category</a>
      <span class="sep" aria-hidden="true">&rarr;</span>
      <span aria-current="page">Page Name</span>
    </nav>

    <div class="rl-eyebrow" aria-label="Topic">
      <span class="dot"></span>
      Topic
      <span class="sep" aria-hidden="true">&middot;</span>
      <strong>Subtitle</strong>
    </div>

    <h1 id="article-title">Article Title Here</h1>

    <div class="rl-meta" aria-label="Primary sources">
      <strong>Primary sources:</strong>
      <a href="#" target="_blank" rel="noopener noreferrer">Source Name</a>
    </div>

    <nav class="rl-pills" aria-label="Jump to section">
      <a class="rl-pill" href="#section-1">Section 1</a>
      <a class="rl-pill" href="#faqs">FAQs</a>
    </nav>

    <p class="rl-hero-lead">Lead paragraph text. First sentence is a standalone answer.</p>

    <p class="rl-hero-lead">
      <span class="rl-next-pill">
        <span class="rl-next-label">Next step:</span>
        <a class="rl-next-link" href="/cta/">Get Your Free Quote</a>
      </span>
    </p>
  </div>
</header>
```

---

## rl-card / rl-card-inner

Generic card container with border, radius, and shadow.

```html
<div class="rl-card">
  <div class="rl-card-inner">
    <h3>Card Title</h3>
    <p>Card content.</p>
  </div>
</div>
```

---

## rl-quick-grid / rl-quick-card

2-column grid of data-dense overview cards. Used in ATF section.

```html
<section class="rl-quick-grid" aria-label="Topic overview">
  <article class="rl-quick-card">
    <h3>Card Title</h3>
    <ul>
      <li><strong>Label:</strong> Fact with data point</li>
      <li><strong>Label:</strong> Another fact</li>
    </ul>
  </article>
  <!-- Repeat for 4 cards -->
</section>
```

---

## rl-faq

FAQ accordion using native `<details>/<summary>`. No JavaScript required.

```html
<div class="rl-faq" aria-label="Topic FAQs">
  <details>
    <summary>What is the question?</summary>
    <div class="ans">The direct answer in 2-3 sentences.</div>
  </details>
  <details>
    <summary>Another question?</summary>
    <div class="ans">Another answer.</div>
  </details>
</div>
```

---

## rl-table-scroll / rl-table

Responsive table with rounded scroll wrapper.

```html
<div class="rl-table-scroll">
  <table class="rl-table">
    <thead>
      <tr><th>Column 1</th><th>Column 2</th></tr>
    </thead>
    <tbody>
      <tr><td>Data</td><td>Data</td></tr>
    </tbody>
  </table>
</div>
```

Add `data-rl-table="scroll"` to force horizontal scrolling on wide tables.

---

## rl-callout

Content callout box with semantic variants.

```html
<div class="rl-callout">
  <h3>Default Callout</h3>
  <p>Content here.</p>
</div>

<div class="rl-callout rl-callout--warning">
  <h3>Warning</h3>
  <p>Amber-tinted callout for cautions.</p>
</div>

<div class="rl-callout rl-callout--info">
  <h3>Info</h3>
  <p>Orange-tinted callout for tips.</p>
</div>

<div class="rl-callout rl-callout--success">
  <h3>Success</h3>
  <p>Green-tinted callout for positive outcomes.</p>
</div>

<div class="rl-callout rl-callout--danger">
  <h3>Danger</h3>
  <p>Red-tinted callout for critical warnings.</p>
</div>
```

---

## rl-disclosure

Resources/references section. Always the last section in an article.

```html
<div class="rl-callout rl-disclosure">
  <h4>Resources Used</h4>
  <ul>
    <li><a href="#" target="_blank" rel="noopener noreferrer">Source Name</a></li>
  </ul>
</div>
```

---

## rl-bullet-section

Colored info boxes with left accent stripe.

```html
<div class="rl-bullet-section rl-bullet-section--green">
  <strong>Title</strong>
  <ul>
    <li>Point one</li>
    <li>Point two</li>
  </ul>
</div>
```

**Variants:** `--green`, `--yellow`, `--red`, `--blue`, `--gray`

---

## rl-next-pill

CTA pill with label + link. Used in hero and mid-article.

```html
<span class="rl-next-pill">
  <span class="rl-next-label">Next step:</span>
  <a class="rl-next-link" href="/cta/">CTA Text</a>
</span>
```

---

## rl-btn

Button component with primary/secondary/accent variants.

```html
<a class="rl-btn rl-btn--primary" href="#">Primary Button</a>
<a class="rl-btn rl-btn--secondary" href="#">Secondary Button</a>
<a class="rl-btn rl-btn--accent" href="#">Accent Button</a>
<a class="rl-btn rl-btn--secondary rl-btn--sm" href="#">Small Button</a>
```

---

## rl-grid-2 / rl-grid-3

Responsive grid layouts that stack on mobile.

```html
<div class="rl-grid-2">
  <div>Column 1</div>
  <div>Column 2</div>
</div>

<div class="rl-grid-3">
  <div>Column 1</div>
  <div>Column 2</div>
  <div>Column 3</div>
</div>
```

---

## Utility Classes

| Class | Purpose |
|-------|---------|
| `rl-mt-{xs,sm,md,lg,xl}` | Margin top |
| `rl-mb-{xs,sm,md,lg,xl}` | Margin bottom |
| `rl-text-{left,center,right}` | Text alignment |
| `rl-text-{primary,accent,muted}` | Text color |
| `rl-flex` | Display flex |
| `rl-sr-only` | Screen reader only |
| `rl-hide` | Display none |
| `rl-skip` | Accessible skip link |
