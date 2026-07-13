// Compact — dense single-column CV for engineers. IBM Plex Sans body with
// Plex Mono metadata, maximal information per square centimeter while staying
// scannable. No photo variant looks best, but photo is supported (small,
// top right).

#import "/typst/common.typ": *

#let _section(title, accent, p) = {
  v(p.sect-above * 0.9, weak: true)
  grid(
    columns: (auto, auto, 1fr),
    column-gutter: 6pt,
    align: (horizon, horizon, horizon),
    text(font: "IBM Plex Mono", size: p.h, weight: 500, fill: rgb(accent), "//"),
    text(size: p.h, weight: 700, tracking: 0.07em, fill: ink, upper(title)),
    line(length: 100%, stroke: 0.5pt + rgb("#d8dce2")),
  )
  v(p.sect-below * 0.9, weak: true)
}

#let render(data, settings, photo: none) = {
  let p = density-params(settings)
  let accent = settings.at("accent", default: "#0E8A66")

  set page(paper: "a4", margin: (x: p.margin-x - 0.1cm, top: p.margin-y - 0.05cm, bottom: p.margin-y - 0.05cm))
  set text(font: "IBM Plex Sans", size: p.base, fill: ink, lang: settings.at("lang", default: "en"))
  set par(leading: p.leading, justify: false, spacing: p.par-gap)

  // ---- Header ---------------------------------------------------------------
  let contacts = data.at("contacts", default: (:))
  let pairs = contact-pairs(contacts)
  let head-left = {
    text(size: p.name * 0.92, weight: 700, tracking: -0.01em, fill: ink, data.full_name)
    if has(data.at("headline", default: none)) {
      h(10pt)
      box(baseline: -22%, rect(
        fill: rgb(accent).lighten(88%),
        stroke: 0.5pt + rgb(accent).lighten(55%),
        radius: 2.5pt,
        inset: (x: 5.5pt, y: 3.2pt),
        text(size: p.small, weight: 600, fill: rgb(accent).darken(18%), data.headline),
      ))
    }
    if pairs.len() > 0 {
      v(4.5pt, weak: true)
      let items = pairs.map(((kind, value)) => box(contact-item(
        kind, value, color: accent, text-fill: muted, size: p.small,
      )))
      items.join(h(0.75em))
    }
  }
  if photo != none {
    grid(
      columns: (1fr, auto),
      column-gutter: 12pt,
      align: (left + horizon, right + horizon),
      head-left,
      photo-box(photo, p.photo * 0.82, shape: "square"),
    )
  } else {
    head-left
  }
  v(3pt, weak: true)
  line(length: 100%, stroke: 1pt + ink)

  // ---- Summary ----------------------------------------------------------------
  if has(data.at("summary", default: none)) {
    v(p.sect-below, weak: true)
    text(size: p.base, fill: ink.lighten(8%), data.summary)
  }

  // ---- Experience ---------------------------------------------------------------
  let experience = data.at("experience", default: ())
  if experience.len() > 0 {
    _section(label-for(settings, "experience"), accent, p)
    for (i, job) in experience.enumerate() {
      if i > 0 { v(p.entry-gap * 0.85, weak: true) }
      grid(
        columns: (1fr, auto),
        column-gutter: 8pt,
        {
          text(size: p.base, weight: 600, fill: ink, getstr(job, "title"))
          let company = getstr(job, "company")
          if company != "" {
            text(size: p.base, fill: muted, "  @ ")
            text(size: p.base, weight: 500, fill: rgb(accent).darken(10%), company)
          }
        },
        text(
          font: "IBM Plex Mono", size: p.small * 0.95, fill: faint,
          (date-range(job), getstr(job, "location")).filter(b => b != "").join(" · "),
        ),
      )
      for b in job.at("bullets", default: ()) {
        v(p.bullet-gap, weak: true)
        grid(
          columns: (8pt, 1fr),
          column-gutter: 2pt,
          text(size: p.small, fill: rgb(accent), "–"),
          text(size: p.base, fill: ink.lighten(8%), b),
        )
      }
    }
  }

  // ---- Projects -------------------------------------------------------------------
  let projects = data.at("projects", default: ())
  if projects.len() > 0 {
    _section(label-for(settings, "projects"), accent, p)
    for (i, proj) in projects.enumerate() {
      if i > 0 { v(p.entry-gap * 0.7, weak: true) }
      grid(
        columns: (1fr, auto),
        column-gutter: 8pt,
        text(size: p.base, weight: 600, fill: ink, getstr(proj, "name")),
        text(font: "IBM Plex Mono", size: p.small * 0.95, fill: faint, getstr(proj, "tech")),
      )
      if has(proj.at("description", default: none)) {
        v(1.3pt, weak: true)
        text(size: p.base, fill: ink.lighten(8%), proj.description)
      }
    }
  }

  // ---- Skills as compact tag rows ----------------------------------------------------
  let skills = data.at("skills", default: ())
  if skills.len() > 0 {
    _section(label-for(settings, "skills"), accent, p)
    for (i, group) in skills.enumerate() {
      if i > 0 { v(2.2pt, weak: true) }
      grid(
        columns: (auto, 1fr),
        column-gutter: 7pt,
        text(font: "IBM Plex Mono", size: p.small * 0.95, weight: 500, fill: rgb(accent).darken(12%), getstr(group, "category") + ":"),
        text(size: p.small, fill: ink.lighten(10%), group.at("items", default: ()).join(" · ")),
      )
    }
  }

  // ---- Education --------------------------------------------------------------------
  let education = data.at("education", default: ())
  if education.len() > 0 {
    _section(label-for(settings, "education"), accent, p)
    for (i, ed) in education.enumerate() {
      if i > 0 { v(p.entry-gap * 0.7, weak: true) }
      grid(
        columns: (1fr, auto),
        column-gutter: 8pt,
        {
          text(size: p.base, weight: 600, fill: ink, getstr(ed, "degree"))
          let school = getstr(ed, "school")
          if school != "" {
            text(size: p.base, fill: muted, " · " + school)
          }
        },
        text(
          font: "IBM Plex Mono", size: p.small * 0.95, fill: faint,
          (date-range(ed), getstr(ed, "location")).filter(b => b != "").join(" · "),
        ),
      )
      let details = ed.at("details", default: ())
      if details.len() > 0 {
        v(1.3pt, weak: true)
        text(size: p.small, fill: muted, details.join("  ·  "))
      }
    }
  }

  // ---- Footer line: certifications, languages, interests ------------------------------
  let certifications = data.at("certifications", default: ())
  let langs = data.at("languages", default: ())
  let interests = data.at("interests", default: ())
  if certifications.len() > 0 or langs.len() > 0 or interests.len() > 0 {
    _section(label-for(settings, "languages"), accent, p)
    if certifications.len() > 0 {
      text(size: p.small, fill: ink.lighten(6%), certifications.map(c => {
        (getstr(c, "name"), getstr(c, "year")).filter(b => b != "").join(" ")
      }).join("  ·  "))
      v(2.2pt, weak: true)
    }
    if langs.len() > 0 {
      text(size: p.small, fill: ink.lighten(6%), langs.map(l => {
        let lvl = getstr(l, "level")
        if lvl != "" { getstr(l, "name") + " (" + lvl + ")" } else { getstr(l, "name") }
      }).join("  ·  "))
    }
    if interests.len() > 0 {
      v(2.2pt, weak: true)
      text(size: p.small, fill: muted, interests.join("  ·  "))
    }
  }

  end-anchor()
}
