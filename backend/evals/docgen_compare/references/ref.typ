// Reference CV, hand-written Typst baseline for the docgen comparison bench.
// Standalone (no app template imports), compiles with plain `typst compile`.
#let accent = rgb("#0F62FE")
#let dim = luma(35%)

#set page(paper: "a4", margin: (x: 1.4cm, y: 1.2cm))
#set text(size: 9.8pt)
#set par(leading: 0.6em)
#set list(indent: 0.9em, spacing: 0.55em, marker: text(fill: accent)[•])

#show heading.where(level: 2): it => block(above: 1em, below: 0.5em)[
  #text(size: 10pt, weight: "bold", fill: accent, tracking: 0.5pt, upper(it.body))
  #v(-3pt)
  #line(length: 100%, stroke: 0.6pt + accent.lighten(50%))
]

#let entry(title, org, meta, bullets) = block(above: 0.75em)[
  #grid(
    columns: (1fr, auto),
    column-gutter: 8pt,
    [*#title* · #org],
    text(size: 8.5pt, fill: dim, meta),
  )
  #if bullets.len() > 0 { list(..bullets) }
]

#text(size: 20pt, weight: "bold")[Alex Martin]
#v(-4pt)
#text(fill: accent, weight: "semibold")[Machine Learning Engineer — LLM Systems & MLOps]
#v(-5pt)
#text(size: 8.5pt, fill: dim, "alex.martin@example.com · +33 6 12 34 56 78 · Paris, France · linkedin.com/in/alex-martin-ml · github.com/alexmartin-ml · alexmartin.dev")

== Summary
ML engineer with 4 years of experience taking LLM and computer-vision systems from prototype to production. Designed RAG platforms serving 40k daily queries, cut inference costs by 35%, and led the MLOps practice for a 12-person data team. Looking to build AI products that survive contact with real users.

== Experience
#entry("Machine Learning Engineer", "Lumina AI", "Paris, France · Jan 2024 – Present", (
  "Architected the retrieval-augmented generation platform behind the flagship assistant: hybrid BM25 + dense retrieval, reranking, and grounded citation checks serving 40k queries/day at p95 < 900 ms.",
  "Cut LLM serving costs 35% by routing between fine-tuned small models and frontier APIs based on query complexity scoring.",
  "Built the evaluation harness (LLM-as-judge + golden sets) that gates every prompt and model change in CI.",
))
#entry("Data Scientist", "Nexa Retail Group", "Lille, France · Sep 2021 – Dec 2023", (
  "Shipped demand-forecasting models (gradient boosting, hierarchical reconciliation) covering 1,200 stores, reducing stockouts 18%.",
  "Industrialized the feature pipeline on Spark + Airflow; training-to-deploy time fell from 3 weeks to 2 days.",
  "Mentored two junior data scientists and ran the team's paper-reading group.",
))
#entry("Research Intern — Computer Vision", "INRIA", "Grenoble, France · Feb 2021 – Aug 2021", (
  "Implemented self-supervised pretraining (SimCLR variants) for defect detection on industrial imagery; +9 mAP over the supervised baseline with 10x less labeled data.",
))

== Education
#entry("MSc Computer Science — Machine Learning", "Université Grenoble Alpes", "Grenoble · 2019 – 2021", (
  "Thesis: contrastive pretraining for industrial vision. Graduated with highest honors.",
))
#entry("BSc Mathematics & Computer Science", "Université de Lille", "Lille · 2016 – 2019", ())

== Skills
*ML & LLM:* PyTorch, RAG, fine-tuning (LoRA), evaluation, vLLM, embeddings \
*Data & Infra:* Python, SQL, Spark, Airflow, Kafka, Postgres \
*MLOps & Cloud:* Docker, Kubernetes, GCP (Vertex, Cloud Run), CI/CD, monitoring & drift

== Projects
#entry("OpenRecruit", "FastAPI, React, Typst", "", (
  "Open-source CV tailoring tool: structured generation with schema-enforced LLM output and millisecond document rendering.",
))
#entry("GPU cost dashboard", "Grafana, Prometheus", "", (
  "Real-time per-team GPU utilization and cost attribution adopted by 3 squads.",
))

== Languages & Certifications
*Languages:* French (native), English (C1), Spanish (B1) \
*Certifications:* GCP Professional ML Engineer, Google Cloud, 2024 \
*Interests:* Trail running, Chess (1800 ELO), Synthesizers
