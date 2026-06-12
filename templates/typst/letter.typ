// Cover letter (lettre de motivation). Typography pairs with the chosen CV
// template family: onyx/compact -> Plex Sans, classic -> Plex Serif.

#import "/typst/common.typ": *

#let render(data, settings, photo: none) = {
  let p = density-params(settings)
  let accent = settings.at("accent", default: "#0F62FE")
  let family = if settings.at("template", default: "onyx") == "classic" {
    "IBM Plex Serif"
  } else {
    "IBM Plex Sans"
  }

  set page(paper: "a4", margin: (x: 2.1cm, top: 1.7cm, bottom: 1.7cm))
  set text(font: family, size: 10.6pt, fill: ink, lang: settings.at("lang", default: "en"))
  set par(leading: 0.68em, justify: true, spacing: 0.9em)

  let sender = data.at("sender", default: (:))
  let recipient = data.at("recipient", default: (:))

  // ---- Sender header --------------------------------------------------------
  text(size: 16.5pt, weight: 700, tracking: -0.01em, fill: ink, getstr(sender, "full_name"))
  v(3pt, weak: true)
  {
    let bits = ()
    if has(sender.at("location", default: none)) { bits.push(getstr(sender, "location")) }
    if has(sender.at("phone", default: none)) { bits.push(getstr(sender, "phone")) }
    if has(sender.at("email", default: none)) { bits.push(getstr(sender, "email")) }
    if bits.len() > 0 {
      text(size: 9pt, fill: muted, bits.join("   ·   "))
    }
  }
  v(4pt, weak: true)
  line(length: 100%, stroke: 1pt + rgb(accent))
  v(14pt, weak: true)

  // ---- Recipient block + date ------------------------------------------------
  grid(
    columns: (1fr, auto),
    align: (left + top, right + top),
    {
      if has(recipient.at("name", default: none)) {
        text(size: 10.6pt, weight: 600, getstr(recipient, "name"))
        linebreak()
      }
      if has(recipient.at("company", default: none)) {
        text(size: 10.6pt, weight: 500, fill: ink.lighten(8%), getstr(recipient, "company"))
        linebreak()
      }
      for line in recipient.at("address_lines", default: ()) {
        text(size: 9.6pt, fill: muted, line)
        linebreak()
      }
    },
    text(size: 9.6pt, fill: muted, getstr(data, "date_str")),
  )
  v(13pt, weak: true)

  // ---- Subject ------------------------------------------------------------------
  if has(data.at("subject", default: none)) {
    text(size: 10.8pt, weight: 600, fill: rgb(accent).darken(12%), getstr(data, "subject"))
    v(11pt, weak: true)
  }

  // ---- Body -----------------------------------------------------------------------
  if has(data.at("greeting", default: none)) {
    text(data.greeting)
    v(7pt, weak: true)
  }
  for para in data.at("paragraphs", default: ()) {
    par(text(para))
  }
  if has(data.at("closing", default: none)) {
    v(7pt, weak: true)
    par(text(data.closing))
  }

  // ---- Signature ---------------------------------------------------------------------
  v(20pt, weak: true)
  align(right, text(size: 11.2pt, weight: 600, getstr(data, "signature")))
}
