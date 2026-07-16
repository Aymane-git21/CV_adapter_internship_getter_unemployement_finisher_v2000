// Classic — traditional serif CV. IBM Plex Serif, centered header, hairline
// rules, dates in a left column. At home in French corporate and academic
// applications. Optional rounded-square photo.

#import "/typst/common.typ": *

#let _section(title, accent, p) = {
  v(p.sect-above, weak: true)
  text(size: p.h, weight: 600, tracking: 0.13em, fill: rgb(accent).darken(15%), upper(title))
  v(2.5pt, weak: true)
  line(length: 100%, stroke: 0.5pt + rgb(accent).lighten(30%))
  v(p.sect-below, weak: true)
}

// date-left layout: 3cm date column, content right.
#let _row(dates, body, p) = {
  grid(
    columns: (3cm, 1fr),
    column-gutter: 10pt,
    text(size: p.small, fill: muted, style: "italic", dates),
    body,
  )
}

#let render(data, settings, photo: none) = {
  let p = density-params(settings)
  let accent = settings.at("accent", default: "#1C3B5A")

  set page(paper: "a4", margin: (x: p.margin-x + 0.25cm, top: p.margin-y, bottom: p.margin-y))
  set text(font: "IBM Plex Serif", size: p.base, fill: ink, lang: settings.at("lang", default: "en"))
  set par(leading: p.leading, justify: true, spacing: p.par-gap)

  // ---- Header: centered, photo floats right when present --------------------
  let contacts = data.at("contacts", default: (:))
  let pairs = contact-pairs(contacts)
  let head = {
    set align(center)
    text(size: p.name, weight: 600, tracking: 0.01em, fill: ink, data.full_name)
    if has(data.at("headline", default: none)) {
      v(3.5pt, weak: true)
      text(size: p.headline, style: "italic", fill: rgb(accent).darken(10%), data.headline)
    }
    if pairs.len() > 0 {
      v(5pt, weak: true)
      contact-row(pairs, accent, text-fill: muted, size: p.small, gap: 0.8em)
    }
  }
  if photo != none {
    grid(
      columns: (p.photo, 1fr, p.photo),
      column-gutter: 8pt,
      align: (left + horizon, center + horizon, right + horizon),
      [],
      head,
      photo-box(photo, p.photo, shape: "square"),
    )
  } else {
    head
  }
  v(5pt, weak: true)
  line(length: 100%, stroke: 0.9pt + rgb(accent).darken(10%))
  v(1.4pt, weak: true)
  line(length: 100%, stroke: 0.4pt + rgb(accent).lighten(35%))

  // ---- Summary ---------------------------------------------------------------
  if has(data.at("summary", default: none)) {
    _section(label-for(settings, "summary"), accent, p)
    text(size: p.base, data.summary)
  }

  // ---- Experience ------------------------------------------------------------
  let experience = data.at("experience", default: ())
  if experience.len() > 0 {
    _section(label-for(settings, "experience"), accent, p)
    for (i, job) in experience.enumerate() {
      if i > 0 { v(p.entry-gap, weak: true) }
      _row(date-range(job), {
        text(size: p.base, weight: 600, fill: ink, getstr(job, "title"))
        let org-bits = (getstr(job, "company"), getstr(job, "location")).filter(b => b != "")
        if org-bits.len() > 0 {
          linebreak()
          text(size: p.small, style: "italic", fill: muted, org-bits.join(" · "))
        }
        for b in job.at("bullets", default: ()) {
          v(p.bullet-gap, weak: true)
          grid(
            columns: (7pt, 1fr),
            column-gutter: 3pt,
            text(size: p.small, fill: rgb(accent), "•"),
            text(size: p.base, fill: ink.lighten(6%), b),
          )
        }
      }, p)
    }
  }

  // ---- Education ---------------------------------------------------------------
  let education = data.at("education", default: ())
  if education.len() > 0 {
    _section(label-for(settings, "education"), accent, p)
    for (i, ed) in education.enumerate() {
      if i > 0 { v(p.entry-gap, weak: true) }
      _row(date-range(ed), {
        text(size: p.base, weight: 600, fill: ink, getstr(ed, "degree"))
        let org-bits = (getstr(ed, "school"), getstr(ed, "location")).filter(b => b != "")
        if org-bits.len() > 0 {
          linebreak()
          text(size: p.small, style: "italic", fill: muted, org-bits.join(" · "))
        }
        let details = ed.at("details", default: ())
        if details.len() > 0 {
          v(1.6pt, weak: true)
          text(size: p.small, fill: muted, details.join("  ·  "))
        }
      }, p)
    }
  }

  // ---- Projects ----------------------------------------------------------------
  let projects = data.at("projects", default: ())
  if projects.len() > 0 {
    _section(label-for(settings, "projects"), accent, p)
    for (i, proj) in projects.enumerate() {
      if i > 0 { v(p.entry-gap * 0.7, weak: true) }
      _row(getstr(proj, "tech"), {
        text(size: p.base, weight: 600, fill: ink, getstr(proj, "name"))
        if has(proj.at("description", default: none)) {
          linebreak()
          text(size: p.base, fill: ink.lighten(6%), proj.description)
        }
      }, p)
    }
  }

  // ---- Skills --------------------------------------------------------------------
  let skills = data.at("skills", default: ())
  if skills.len() > 0 {
    _section(label-for(settings, "skills"), accent, p)
    for (i, group) in skills.enumerate() {
      if i > 0 { v(2.4pt, weak: true) }
      _row(getstr(group, "category"), text(size: p.base, fill: ink.lighten(4%), group.at("items", default: ()).join("  ·  ")), p)
    }
  }

  // ---- Certifications ---------------------------------------------------------------
  let certifications = data.at("certifications", default: ())
  if certifications.len() > 0 {
    _section(label-for(settings, "certifications"), accent, p)
    for cert in certifications {
      let bits = (getstr(cert, "name"), getstr(cert, "issuer"), getstr(cert, "year"))
      text(size: p.small, bits.filter(b => b != "").join("  ·  "))
      linebreak()
    }
  }

  // ---- Languages & interests ---------------------------------------------------------
  let langs = data.at("languages", default: ())
  let interests = data.at("interests", default: ())
  if langs.len() > 0 {
    _section(label-for(settings, "languages"), accent, p)
    let parts = langs.map(l => {
      let lvl = getstr(l, "level")
      if lvl != "" {
        [#text(weight: 600, size: p.base, getstr(l, "name")) #text(size: p.small, fill: muted, "(" + lvl + ")")]
      } else {
        text(weight: 600, size: p.base, getstr(l, "name"))
      }
    })
    parts.join(text(fill: faint, "    ·    "))
  }
  if interests.len() > 0 {
    _section(label-for(settings, "interests"), accent, p)
    text(size: p.base, fill: ink.lighten(6%), interests.join("  ·  "))
  }

  end-anchor()
}
