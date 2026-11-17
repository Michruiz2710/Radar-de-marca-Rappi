#!/usr/bin/env bash
# Simula un fallo para probar las alertas (P3.2) y mide cuánto tarda Grafana en dispararla.
#
#   scripts/simular_fallo.sh inyectar [A1|A4|A7]   publica métricas de fallo en el Pushgateway (por defecto A1)
#   scripts/simular_fallo.sh real                  lanza 2 corridas reales en Prefect que fallan al instante (fuente inválida)
#   scripts/simular_fallo.sh minio                 apaga MinIO: el scraper falla de verdad, pero tarda unos 5 min en agotar reintentos
#   scripts/simular_fallo.sh restaurar             borra lo simulado y vuelve a dejar todo normal
#
# Se corre desde cualquier carpeta del repositorio, con el entorno levantado (make up).
# Variables opcionales: ENTORNO (dev por defecto), PUSHGATEWAY_PORT, GRAFANA_PORT,
# GRAFANA_ADMIN_USER y GRAFANA_ADMIN_PASSWORD (si no se pasan, se leen de .env).

set -euo pipefail
cd "$(dirname "$0")/.."

ENTORNO="${ENTORNO:-dev}"
COMPOSE=(docker compose -f infra/docker-compose.yml --env-file .env --env-file "config/${ENTORNO}.env")
ESPERA_MAXIMA=300 # el criterio de P3.2 es que la alerta P0 llegue en menos de 5 minutos

leer_env() { # leer_env NOMBRE -> valor en .env (vacío si no está)
  local linea
  linea=$(grep -E "^$1=" .env 2>/dev/null | tail -1) || true
  printf '%s' "${linea#*=}" | tr -d '\r'
}

PUSH_PORT="${PUSHGATEWAY_PORT:-$(leer_env PUSHGATEWAY_PORT)}"
PUSH_URL="http://localhost:${PUSH_PORT:-9091}/metrics/job/radar_simulacion"
GF_PORT="${GRAFANA_PORT:-$(leer_env GRAFANA_PORT)}"
GRAFANA_URL="http://localhost:${GF_PORT:-3000}"
GF_USER="${GRAFANA_ADMIN_USER:-$(leer_env GRAFANA_ADMIN_USER)}"
GF_PASS="${GRAFANA_ADMIN_PASSWORD:-$(leer_env GRAFANA_ADMIN_PASSWORD)}"
GF_USER="${GF_USER:-admin}"

PYTHON=""
for candidato in python3 python; do
  if command -v "$candidato" > /dev/null 2>&1; then PYTHON="$candidato"; break; fi
done

uso() { sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-1}"; }

publicar() { curl -fsS --max-time 10 --data-binary @- "$PUSH_URL" > /dev/null; }

# Estado de una alerta en Grafana: imprime firing, pending, inactive... o "desconocido"
estado_alerta() {
  local id="$1" respuesta
  [ -n "$PYTHON" ] && [ -n "$GF_PASS" ] || { echo desconocido; return; }
  respuesta=$(curl -fsS --max-time 10 -u "$GF_USER:$GF_PASS" "$GRAFANA_URL/api/prometheus/grafana/api/v1/rules" 2> /dev/null) || { echo desconocido; return; }
  printf '%s' "$respuesta" | "$PYTHON" -c "
import json, sys
estados = [r.get('state', 'inactive') for g in json.load(sys.stdin)['data']['groups'] for r in g['rules'] if r['name'].startswith(sys.argv[1] + ' ')]
print('firing' if 'firing' in estados else (estados[0] if estados else 'desconocido'))
" "$id" 2> /dev/null || echo desconocido
}

esperar_alerta() { # esperar_alerta ID INICIO
  local id="$1" inicio="$2" estado
  if [ "$(estado_alerta "$id")" = "desconocido" ]; then
    echo "No pude consultar Grafana ($GRAFANA_URL): revisa la alerta $id a mano en Alerting > Alert rules y en tu correo."
    return 0
  fi
  echo "Esperando a que Grafana dispare $id (máximo ${ESPERA_MAXIMA} s)..."
  while [ $(( $(date +%s) - inicio )) -lt "$ESPERA_MAXIMA" ]; do
    estado=$(estado_alerta "$id")
    if [ "$estado" = "firing" ]; then
      echo "✔ $id está en estado Firing a los $(( $(date +%s) - inicio )) s. El correo sale en segundos (las P0 no esperan; las P1, hasta 30 s)."
      return 0
    fi
    sleep 5
  done
  echo "✘ $id no se disparó en ${ESPERA_MAXIMA} s. Revisa Prometheus (¿ve las métricas?) y Alerting > Alert rules." >&2
  return 1
}

alerta_activa() { [ "$(estado_alerta "$1")" = "firing" ]; }

inyectar() {
  local id="${1:-A1}" inicio
  id=$(printf '%s' "$id" | tr '[:lower:]' '[:upper:]')
  case "$id" in A1 | A4 | A7) ;; *) echo "Solo se puede inyectar A1, A4 o A7." >&2; exit 1 ;; esac
  if alerta_activa "$id"; then
    echo "Aviso: $id ya estaba en Firing antes de empezar; la medición no valdría. Corre 'restaurar' y revisa la causa real." >&2
  fi
  inicio=$(date +%s)
  case "$id" in
    A1) # un flujo con 2 corridas fallidas seguidas
      printf '# TYPE fallas_consecutivas gauge\nfallas_consecutivas{flujo="pipeline:simulacion"} 2\n' | publicar ;;
    A4) # una validación crítica fallida: la regla mira el aumento del contador, por eso se publican dos valores
      printf '# TYPE validaciones_fallidas_total counter\nvalidaciones_fallidas_total{suite="simulacion",severidad="critica"} 0\n' | publicar
      echo "Esperando 40 s a que Prometheus lea el valor inicial..."
      sleep 40
      printf '# TYPE validaciones_fallidas_total counter\nvalidaciones_fallidas_total{suite="simulacion",severidad="critica"} 1\n' | publicar ;;
    A7) # cuota de YouTube por encima del 80 %
      printf '# TYPE cuota_youtube_usada gauge\ncuota_youtube_usada{simulacion="si"} 8500\n' | publicar ;;
  esac
  echo "Fallo $id publicado en el Pushgateway (grupo radar_simulacion; no toca las métricas reales)."
  esperar_alerta "$id" "$inicio"
  echo "Cuando termines: scripts/simular_fallo.sh restaurar"
}

real() {
  local inicio
  inicio=$(date +%s)
  echo "Lanzando 2 corridas de ${ENTORNO} con una fuente inválida: fallan al instante, sin reintentos."
  # Son corridas reales de Prefect: quedan en Failed y el gancho de fallo publica las métricas.
  # El flujo aparece como pipeline:simulacion, así que no se mezcla con los flujos reales.
  for _ in 1 2; do
    "${COMPOSE[@]}" exec -T orquestador prefect deployment run "pipeline/todas-${ENTORNO}" --param 'fuentes=["simulacion"]' > /dev/null
  done
  esperar_alerta A1 "$inicio"
  echo "Cuando termines: scripts/simular_fallo.sh restaurar"
}

minio() {
  local inicio respuesta
  echo "Esto apaga MinIO y hace fallar de verdad las corridas de noticias del entorno ${ENTORNO}."
  echo "Cada corrida agota sus reintentos: tarda unos 5 minutos, más que el criterio de la alerta."
  printf '¿Continuar? [s/N] '
  read -r respuesta
  [ "$respuesta" = "s" ] || [ "$respuesta" = "S" ] || { echo "Cancelado."; exit 0; }
  inicio=$(date +%s)
  "${COMPOSE[@]}" stop minio
  # Dos corridas a la vez: cada una suma una falla (A1 pide 2 seguidas)
  for _ in 1 2; do
    "${COMPOSE[@]}" exec -T orquestador prefect deployment run "pipeline/news-${ENTORNO}" > /dev/null
  done
  ESPERA_MAXIMA=600 esperar_alerta A1 "$inicio" || true
  echo "Cuando termines: scripts/simular_fallo.sh restaurar, y lanza una corrida exitosa de noticias para poner en 0 sus fallas."
}

restaurar() {
  curl -fsS --max-time 10 -X DELETE "$PUSH_URL" > /dev/null && echo "Métricas simuladas borradas del Pushgateway."
  # Quita del estado del orquestador el flujo pipeline:simulacion (lo crea el modo `real`) y vuelve a publicar
  if "${COMPOSE[@]}" exec -T orquestador python -c "
from src.observability import metricas as m
with m._bloqueo():
    estado = m._leer()
    quitado = estado['flujos'].pop('pipeline:simulacion', None)
    m._guardar(estado)
m.publicar(estado)
print('Flujo simulado borrado del estado.' if quitado else 'No había flujo simulado en el estado.')
" 2> /dev/null; then :; else echo "(el orquestador no está corriendo: no se limpió el estado del flujo simulado)"; fi
  # Solo si MinIO estaba apagado (por el modo `real`); no hace nada si ya corre
  if [ -z "$("${COMPOSE[@]}" ps --status running --services 2> /dev/null | grep -x minio)" ]     && [ -n "$("${COMPOSE[@]}" ps -a --services 2> /dev/null | grep -x minio)" ]; then
    "${COMPOSE[@]}" start minio > /dev/null && echo "MinIO encendido."
  fi
  echo "Para poner en 0 las fallas de una corrida real, deja que corra una exitosa o lánzala a mano:"
  echo "  ${COMPOSE[*]} exec orquestador prefect deployment run 'pipeline/news-${ENTORNO}'"
  echo "Las alertas pasan a Resuelta en un par de minutos y Grafana envía el aviso [RESOLVED]."
}

case "${1:-}" in
  inyectar) inyectar "${2:-A1}" ;;
  real) real ;;
  minio) minio ;;
  restaurar) restaurar ;;
  -h | --help | help) uso 0 ;;
  *) uso 1 ;;
esac
