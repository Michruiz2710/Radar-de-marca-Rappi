# Radar de Marca: Rappi

Pipeline DataOps de escucha activa que recolecta lo que se dice de Rappi en Google Play, YouTube y Reddit, valida y analiza esos datos, alerta cuando algo falla o el sentimiento negativo se dispara, y lo muestra en un dashboard de negocio.

Proyecto grupal del curso **Enfoque DataOps** — Escuela Colombiana de Ingeniería Julio Garavito.

> Proyecto académico. No está afiliado, patrocinado ni avalado por Rappi. Rappi se usa únicamente como caso de estudio con datos públicos de plataformas de terceros.

## Equipo

| Integrante | Rol nominal |
| --- | --- |
| Sara | Data Engineer |
| Katalina | Data Quality Analyst |
| Gabriel | DevOps/Platform Engineer |
| Jonathan | Data Analyst/Scientist |
| Michelle | Observability & Monitoring Lead · Coordinación |

La ruta de trabajo completa (paquetes, autores, coautores, revisores y fechas) está en el documento del proyecto.

## Arquitectura

```
Google Play ─┐
YouTube ─────┼─► Scrapers (Docker) ─► MinIO (raw) ─► Limpieza + Great Expectations + NLP ─► Postgres (clean)
Google News ─┘                                                                                  │
                                                                                                ▼
                                                    Dashboard (Streamlit) ◄── dbt ─► Postgres (analytics)

Prefect orquesta cada paso · Prometheus y Grafana observan · GitHub Actions prueba y despliega
```

## Estructura del repositorio

```
.
├── .github/
│   ├── workflows/             # CI/CD (P2.5)
│   ├── ISSUE_TEMPLATE/        # plantilla de issue por paquete
│   ├── CODEOWNERS             # revisor automático por carpeta
│   └── pull_request_template.md
├── config/                    # configuración por entorno: dev, staging, prod (sin secretos)
├── infra/
│   ├── docker-compose.yml     # (P1.1) MinIO, Postgres, Prefect, Prometheus, Grafana, Streamlit
│   ├── prometheus/            # (P3.1)
│   └── grafana/               # (P3.2) dashboards y alertas como código
├── src/
│   ├── common/                # (P1.2) esquema, almacenamiento, privacidad
│   ├── ingestion/
│   │   ├── google_play/       # (P1.3)
│   │   ├── youtube/           # (P1.4)
│   │   └── news/              # (P1.5)
│   ├── transform/
│   │   ├── clean/             # (P2.3)
│   │   └── nlp/               # (P2.4)
│   └── observability/         # (P3.1)
├── flows/                     # (P2.1) flujos de Prefect
├── quality/                   # (P2.2) suites de Great Expectations
├── dbt/                       # (P3.4) modelos analíticos
├── dashboard/                 # (P3.3) app de Streamlit
├── data/etiquetas/            # (P1.5) muestra etiquetada, únicos datos versionados
├── docs/                      # contrato de datos, catálogo, linaje, runbooks
├── scripts/                   # utilidades y simulación de fallos
├── tests/                     # pruebas automatizadas
├── .env.example               # variables de entorno de referencia
├── Makefile                   # atajos: make up, make down, make test
└── README.md
```

Cada carpeta tiene su propio `README.md` con su propósito, el paquete al que pertenece y quién lo revisa.

## Cómo empezar

Requisitos: Docker Desktop, Python 3.11, Git.

```bash
git clone https://github.com/Michruiz2710/Radar-de-marca-Rappi.git
cd Radar-de-marca-Rappi
cp .env.example .env        # completar con los valores reales (nunca subir .env)
make up                     # disponible cuando se cierre P1.1
```

## Cómo trabajamos

1. Nadie sube cambios directo a `main`; todo entra por Pull Request.
2. Una rama por paquete: `s<semana>/<paquete>`, por ejemplo `s1/scraper-google-play`.
3. Commits con formato `tipo(alcance): descripción`, por ejemplo `feat(youtube): manejar comentarios desactivados`.
4. Cada PR necesita 1 aprobación del revisor asignado (lo asigna `CODEOWNERS`), quien hace el merge con *Squash and merge*.
5. El revisor responde en máximo 24 horas; si no, puede aprobar otro integrante que no sea el autor.

## Entregables

- [ ] **Semana 1 (6 nov):** scrapers en Docker y datos crudos en MinIO — `v0.1.0`
- [ ] **Semana 2 (13 nov):** pipeline orquestado con pruebas de calidad en CI/CD — `v0.2.0`
- [ ] **Semana 3 (20 nov):** demo del pipeline autónomo, alertas y dashboard — `v1.0.0`

## Datos personales

Los autores de reseñas y comentarios se guardan solo como hash SHA-256 con sal (Ley 1581 de 2012, Habeas Data). No se guardan nombres, fotos ni enlaces a perfiles. Los datos recolectados no se versionan en Git y se eliminan al terminar el curso.
