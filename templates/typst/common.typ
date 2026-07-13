// CV Glowup — shared template library.
// Every template consumes the same CVData/LetterData JSON contract and a
// settings dict: (template, accent, density, show_photo, font_scale, lang).

#let ink = rgb("#16181d")
#let muted = rgb("#5c6470")
#let faint = rgb("#9aa1ab")

// ---------------------------------------------------------------------------
// Icons — inline SVG (stroke style), colored at call time. No icon fonts.
// ---------------------------------------------------------------------------
#let _icon-paths = (
  mail: "<rect x='2.5' y='5' width='19' height='14' rx='2'/><path d='m3 7 9 6 9-6'/>",
  phone: "<path d='M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z'/>",
  pin: "<path d='M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0z'/><circle cx='12' cy='10' r='3'/>",
  globe: "<circle cx='12' cy='12' r='10'/><path d='M2 12h20'/><path d='M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z'/>",
  linkedin: "<path d='M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z'/><rect x='2' y='9' width='4' height='12'/><circle cx='4' cy='4' r='2'/>",
  github: "<path d='M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22'/>",
)

#let icon(name, color: "#5c6470", size: 0.78em) = {
  let body = _icon-paths.at(name, default: none)
  if body != none {
    box(
      baseline: 14%,
      image(
        bytes(
          "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='"
            + color
            + "' stroke-width='2.1' stroke-linecap='round' stroke-linejoin='round'>"
            + body
            + "</svg>",
        ),
        format: "svg",
        height: size,
      ),
    )
  }
}

// ---------------------------------------------------------------------------
// Localized section labels
// ---------------------------------------------------------------------------
#let labels = (
  en: (
    summary: "Profile",
    experience: "Experience",
    education: "Education",
    skills: "Skills",
    projects: "Projects",
    languages: "Languages",
    interests: "Interests",
    certifications: "Certifications",
  ),
  fr: (
    summary: "Profil",
    experience: "Expérience professionnelle",
    education: "Formation",
    skills: "Compétences",
    projects: "Projets",
    languages: "Langues",
    interests: "Centres d'intérêt",
    certifications: "Certifications",
  ),
  de: (
    summary: "Profil",
    experience: "Berufserfahrung",
    education: "Ausbildung",
    skills: "Kenntnisse",
    projects: "Projekte",
    languages: "Sprachen",
    interests: "Interessen",
    certifications: "Zertifikate",
  ),
)

#let label-for(settings, key) = {
  let lang = settings.at("lang", default: "en")
  let pack = labels.at(lang, default: labels.en)
  pack.at(key, default: key)
}

// ---------------------------------------------------------------------------
// Density system — the knob the renderer turns to keep documents on one page.
// All sizes derive from these parameters; font_scale multiplies on top.
// ---------------------------------------------------------------------------
#let density-params(settings) = {
  let density = settings.at("density", default: "normal")
  let scale = settings.at("font_scale", default: 1.0)
  let p = if density == "tight" {
    (
      base: 9.4pt, small: 8.4pt, name: 21.5pt, headline: 10.6pt, h: 9.2pt,
      leading: 0.56em, par-gap: 0.5em,
      sect-above: 8.5pt, sect-below: 4.5pt, entry-gap: 5pt, bullet-gap: 1.6pt,
      margin-y: 0.95cm, margin-x: 1.05cm, photo: 2.15cm,
    )
  } else if density == "xtight" {
    (
      base: 8.9pt, small: 8pt, name: 20pt, headline: 10pt, h: 8.7pt,
      leading: 0.5em, par-gap: 0.42em,
      sect-above: 6.5pt, sect-below: 3.5pt, entry-gap: 3.8pt, bullet-gap: 1.1pt,
      margin-y: 0.85cm, margin-x: 0.95cm, photo: 2cm,
    )
  } else {
    (
      base: 10pt, small: 8.9pt, name: 23.5pt, headline: 11.4pt, h: 9.8pt,
      leading: 0.62em, par-gap: 0.58em,
      sect-above: 11pt, sect-below: 6pt, entry-gap: 7pt, bullet-gap: 2.2pt,
      margin-y: 1.1cm, margin-x: 1.15cm, photo: 2.4cm,
    )
  }
  // Type sizes always follow font_scale. When scaling UP (the renderer's
  // page-fill pass), the fixed pt gaps grow too, so a sparse CV gains
  // proportional whitespace instead of just bigger letters.
  let gap-scale = calc.max(scale, 1.0)
  (
    base: p.base * scale, small: p.small * scale, name: p.name * scale,
    headline: p.headline * scale, h: p.h * scale,
    leading: p.leading, par-gap: p.par-gap,
    sect-above: p.sect-above * gap-scale, sect-below: p.sect-below * gap-scale,
    entry-gap: p.entry-gap * gap-scale, bullet-gap: p.bullet-gap * gap-scale,
    margin-y: p.margin-y, margin-x: p.margin-x, photo: p.photo,
  )
}

// ---------------------------------------------------------------------------
// Small utilities
// ---------------------------------------------------------------------------
#let has(v) = {
  if v == none { return false }
  if type(v) == str { return v.trim() != "" }
  if type(v) == array { return v.len() > 0 }
  true
}

#let getstr(d, key) = {
  let v = d.at(key, default: none)
  if v == none { "" } else if type(v) == str { v } else { str(v) }
}

#let display-url(v) = {
  v.replace("https://", "").replace("http://", "").replace("www.", "").trim("/")
}

#let href(v) = {
  if v.starts-with("http://") or v.starts-with("https://") { v } else { "https://" + v }
}

#let date-range(item) = {
  let s = getstr(item, "start")
  let e = getstr(item, "end")
  if s != "" and e != "" { s + " – " + e } else if s != "" { s } else { e }
}

// One contact item: icon + text (linked when it is a URL/email).
#let contact-item(kind, value, color: "#5c6470", text-fill: muted, size: 8.9pt) = {
  let body = if kind == "mail" {
    link("mailto:" + value, text(fill: text-fill, size: size, value))
  } else if kind in ("linkedin", "github", "globe") {
    link(href(value), text(fill: text-fill, size: size, display-url(value)))
  } else {
    text(fill: text-fill, size: size, value)
  }
  box(icon(kind, color: color, size: size * 0.92)) + h(0.32em) + body
}

// Build the list of (kind, value) contact pairs present in the data.
#let contact-pairs(contacts) = {
  let out = ()
  if has(contacts.at("location", default: none)) { out.push(("pin", contacts.location)) }
  if has(contacts.at("phone", default: none)) { out.push(("phone", contacts.phone)) }
  if has(contacts.at("email", default: none)) { out.push(("mail", contacts.email)) }
  if has(contacts.at("linkedin", default: none)) { out.push(("linkedin", contacts.linkedin)) }
  if has(contacts.at("github", default: none)) { out.push(("github", contacts.github)) }
  if has(contacts.at("website", default: none)) { out.push(("globe", contacts.website)) }
  out
}

// Invisible end-of-content anchor. Zero layout footprint (place() takes the
// element out of the flow); the backend queries <cvg-end> to measure how much
// of the page the content fills (typstsvc.renderer.measure_fill).
#let end-anchor() = place(
  context [#metadata((page: here().position().page, y: here().position().y.pt())) <cvg-end>],
)

// Round or rounded-square photo crop.
#let photo-box(photo, size, shape: "circle") = {
  box(
    clip: true,
    radius: if shape == "circle" { 50% } else { 7% },
    width: size,
    height: size,
    image(photo, width: size, height: size, fit: "cover"),
  )
}
