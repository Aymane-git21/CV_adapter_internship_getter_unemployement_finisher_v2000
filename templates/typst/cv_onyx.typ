// Onyx — flagship modern CV. IBM Plex Sans, strong name block, accent rules,
// optional circular photo. Built for tech/business roles.

#import "/typst/common.typ": *

#let _section(title, accent, p) = {
  v(p.sect-above, weak: true)
  grid(
    columns: (auto, 1fr),
    column-gutter: 9pt,
    align: (left + horizon, horizon),
    text(size: p.h, weight: 700, tracking: 0.1em, fill: ink, upper(title)),
    line(length: 100%, stroke: 0.7pt + rgb(accent).lighten(45%)),
  )
  v(p.sect-below, weak: true)
}

#let _entry-head(left-main, left-sub, right-main, right-sub, accent, p) = {
  grid(
    columns: (1fr, auto),
    column-gutter: 8pt,
    row-gutter: 2.4pt,
    text(size: p.base, weight: 600, fill: ink, left-main),
    text(size: p.small, weight: 500, fill: muted, number-type: "lining", right-main),
    text(size: p.small, weight: 500, fill: rgb(accent).darken(6%), left-sub),
    text(size: p.small, fill: faint, right-sub),
  )
}

#let _bullets(items, accent, p) = {
  for b in items {
    v(p.bullet-gap, weak: true)
    grid(
      columns: (8pt, 1fr),
      column-gutter: 3pt,
      text(size: p.small, fill: rgb(accent), baseline: -0.06em, "▸"),
      text(size: p.base, fill: ink.lighten(8%), b),
    )
  }
}

#let render(data, settings, photo: none) = {
  let p = density-params(settings)
  let accent = settings.at("accent", default: "#0F62FE")

  set page(paper: "a4", margin: (x: p.margin-x, top: p.margin-y, bottom: p.margin-y))
  set text(font: "IBM Plex Sans", size: p.base, fill: ink, lang: settings.at("lang", default: "en"))
  set par(leading: p.leading, justify: false, spacing: p.par-gap)

  // ---- Header --------------------------------------------------------------
  let contacts = data.at("contacts", default: (:))
  let pairs = contact-pairs(contacts)
  let header-left = {
    text(size: p.name, weight: 700, tracking: -0.015em, fill: ink, data.full_name)
    if has(data.at("headline", default: none)) {
      v(3.2pt, weak: true)
      text(size: p.headline, weight: 500, fill: rgb(accent).darken(4%), data.headline)
    }
    if pairs.len() > 0 {
      v(5.5pt, weak: true)
      let items = pairs.map(((kind, value)) => box(contact-item(
        kind, value, color: accent, text-fill: muted, size: p.small,
      )))
      items.join(h(0.85em))
    }
  }
  if photo != none {
    grid(
      columns: (1fr, auto),
      column-gutter: 14pt,
      align: (left + horizon, right + horizon),
      header-left,
      photo-box(photo, p.photo, shape: "circle"),
    )
  } else {
    header-left
  }
  v(4pt, weak: true)
  line(length: 100%, stroke: 1.1pt + rgb(accent))

  // ---- Summary ---------------------------------------------------------------
  if has(data.at("summary", default: none)) {
    _section(label-for(settings, "summary"), accent, p)
    text(size: p.base, fill: ink.lighten(6%), data.summary)
  }

  // ---- Experience ------------------------------------------------------------
  let experience = data.at("experience", default: ())
  if experience.len() > 0 {
    _section(label-for(settings, "experience"), accent, p)
    for (i, job) in experience.enumerate() {
      if i > 0 { v(p.entry-gap, weak: true) }
      _entry-head(
        getstr(job, "title"),
        getstr(job, "company"),
        date-range(job),
        getstr(job, "location"),
        accent, p,
      )
      _bullets(job.at("bullets", default: ()), accent, p)
    }
  }

  // ---- Projects ----------------------------------------------------------------
  let projects = data.at("projects", default: ())
  if projects.len() > 0 {
    _section(label-for(settings, "projects"), accent, p)
    for (i, proj) in projects.enumerate() {
      if i > 0 { v(p.entry-gap * 0.75, weak: true) }
      grid(
        columns: (1fr, auto),
        column-gutter: 8pt,
        text(size: p.base, weight: 600, fill: ink, getstr(proj, "name")),
        text(size: p.small, font: "IBM Plex Mono", fill: faint, getstr(proj, "tech")),
      )
      if has(proj.at("description", default: none)) {
        v(1.6pt, weak: true)
        text(size: p.base, fill: ink.lighten(8%), proj.description)
      }
    }
  }

  // ---- Education ---------------------------------------------------------------
  let education = data.at("education", default: ())
  if education.len() > 0 {
    _section(label-for(settings, "education"), accent, p)
    for (i, ed) in education.enumerate() {
      if i > 0 { v(p.entry-gap, weak: true) }
      _entry-head(
        getstr(ed, "degree"),
        getstr(ed, "school"),
        date-range(ed),
        getstr(ed, "location"),
        accent, p,
      )
      let details = ed.at("details", default: ())
      if details.len() > 0 {
        v(1.8pt, weak: true)
        text(size: p.small, fill: muted, details.join("  ·  "))
      }
    }
  }

  // ---- Skills --------------------------------------------------------------------
  let skills = data.at("skills", default: ())
  if skills.len() > 0 {
    _section(label-for(settings, "skills"), accent, p)
    for (i, group) in skills.enumerate() {
      if i > 0 { v(2.6pt, weak: true) }
      grid(
        columns: (auto, 1fr),
        column-gutter: 8pt,
        text(size: p.small, weight: 600, fill: ink, getstr(group, "category")),
        text(size: p.small, fill: muted, group.at("items", default: ()).join("  ·  ")),
      )
    }
  }

  // ---- Certifications ---------------------------------------------------------------
  let certifications = data.at("certifications", default: ())
  if certifications.len() > 0 {
    _section(label-for(settings, "certifications"), accent, p)
    for cert in certifications {
      let bits = (getstr(cert, "name"), getstr(cert, "issuer"), getstr(cert, "year"))
      text(size: p.small, fill: ink.lighten(6%), bits.filter(b => b != "").join(" — "))
      linebreak()
    }
  }

  // ---- Languages & interests, one compact footer row -------------------------------
  let langs = data.at("languages", default: ())
  let interests = data.at("interests", default: ())
  if langs.len() > 0 or interests.len() > 0 {
    _section(
      if langs.len() > 0 { label-for(settings, "languages") } else { label-for(settings, "interests") },
      accent, p,
    )
    if langs.len() > 0 {
      let parts = langs.map(l => {
        let lvl = getstr(l, "level")
        if lvl != "" {
          [#text(weight: 600, size: p.small, fill: ink, getstr(l, "name")) #text(size: p.small, fill: faint, "(" + lvl + ")")]
        } else {
          text(weight: 600, size: p.small, fill: ink, getstr(l, "name"))
        }
      })
      parts.join(text(size: p.small, fill: faint, "   ·   "))
    }
    if interests.len() > 0 {
      if langs.len() > 0 { v(2.6pt, weak: true) }
      text(size: p.small, fill: muted, interests.join("  ·  "))
    }
  }
}
