# AGENTS.md

Guía para agentes que trabajen en este repo. El contexto de negocio y el uso están en `README.md`.

## Qué es

Monitor del rulo MEP → USDT → ARS: consulta precios, evalúa todas las rutas compra × conversión × venta
y avisa por Telegram cuando la mejor supera un umbral. Corre en AWS Lambda cada 2 minutos en horario
de mercado; también corre local (`python3 -m rulo`).

## Mapa del código

| Archivo | Responsabilidad |
|---|---|
| `rulo/__main__.py` | CLI y orquestación de una corrida: horario → fetch → evaluar → decidir → avisar → guardar estado |
| `rulo/lambda_handler.py` | entrypoint de Lambda; `event["args"]` se pasa como argv a `main()` |
| `rulo/models.py` | `Quote` (cotización normalizada), `Venue` (plataforma de un paso), `Route` (cálculo del %) |
| `rulo/sources/` | adaptadores de fuentes de precios (`comparadolar`, `criptoya`) + `build_sources` |
| `rulo/evaluator.py` | valida cotizaciones (faltantes, ≤0, viejas, tasa fuera de rango) y arma las rutas ordenadas |
| `rulo/alerts.py` | máquina de estados open/improve/close (`decide`) y formato HTML de los mensajes |
| `rulo/state.py` | persistencia del estado: `FileStore` local o `DynamoStore` si existe `RULO_STATE_TABLE` |
| `rulo/notifier.py` | Telegram (token por env o SSM) o consola |
| `rulo/market.py` | horario de mercado y fecha local |
| `config.toml` | plataformas, umbrales, horario; se empaqueta dentro del zip de la Lambda |
| `terraform/` | infra: Lambda, DynamoDB, SSM, Scheduler, IAM, logs |

## Comandos

```bash
python3 -m unittest            # tests, sin red; correr siempre después de tocar código
python3 -m rulo --dry-run      # precios reales, sin avisar ni escribir estado
cd terraform && terraform fmt && terraform validate
terraform plan -var-file=dev.tfvars
```

## Reglas

- **Sin dependencias externas.** Solo stdlib. `boto3` se importa de forma diferida y solo en los
  caminos de AWS (`DynamoStore`, token por SSM), porque lo trae el runtime de Lambda.
- **Python 3.11+** (usa `tomllib`); la Lambda corre en 3.13.
- **Fuentes agnósticas.** Una fuente nueva implementa `fetch(pairs: set[str]) -> list[Quote]`, se
  registra en `build_sources` y se referencia con `source = "..."` en `config.toml`. Normalizá en la
  fuente: `bid`/`ask` tienen que incluir comisiones si la API las informa (`totalBid`/`totalAsk`).
- **Plataformas = config, no código.** Agregar o sacar una plataforma es editar `config.toml`.
- **Semántica de precios:** compra MEP y conversión usan `ask`; venta usa `bid`. La tasa de conversión
  es USD por USDT (1,065 significa que 1 USDT cuesta 1,065 USD).
- **Mensajes y comentarios en español**, formato numérico argentino (`1.637,00`) en los avisos.
- Una fuente que falla no tiene que tirar la corrida: se loguea y se sigue con las demás.

## Decisiones de dominio (no revertir sin consultar)

- Solo dólar **MEP** para comprar; el oficial no sirve por regulaciones.
- Excluidos: P2P, Astropay, Xapo y Wallbit (cuentas del exterior que no aceptan USD MEP).
- Umbral mínimo 1%: por debajo no vale la pena gastar los límites de compra.
- Comisiones fijas de red se desprecian.
- Solo opera en horario de mercado (lunes a viernes, 11 a 17, `America/Argentina/Buenos_Aires`).

## Infra y AWS

- Perfiles: aplicar Terraform con `terraform-admin` (default de `var.profile`); `dev-admin` sirve para
  operar (invoke, logs, SSM) pero **no** puede asumir `TerraformExecutionRole`.
- `terraform/backend.conf` y `terraform/*.tfvars` están en `.gitignore` (IDs de cuentas, chat id):
  **nunca** los commitees ni pongas esos valores en archivos versionados. Las plantillas son los `.example`.
- El token de Telegram **nunca** va en Terraform, en el código ni en commits: vive en SSM
  (`/rulo-bot/dev/telegram-bot-token`, `ignore_changes` en TF) y en `.env` local, que está en `.gitignore`.
- El zip de la Lambda lo arma `archive_file` desde `rulo/**/*.py` + `config.toml`; cambiar cualquiera
  de los dos y hacer `terraform apply` redeploya.
- El schedule usa `schedule_expression_timezone`, así que el cron está en hora de Argentina.
- Antes de un `apply` mostrá el plan; no apliques en otras cuentas sin pedirlo.

## Gotchas

- `time` de CriptoYa es la hora de consulta, no de actualización: no sirve para detectar precios congelados.
- comparadolar no da timestamp para USD (`ts = None`, se acepta).
- Hay P2P con valores absurdos en CriptoYa (ej. `mexcp2p` con bid 1850); por eso están fuera de la config.
- `ItemCount` de DynamoDB se actualiza cada ~6 h; para ver el estado usar `get-item` con `pk = "monitor"`.
- launchd no ve los shims de pyenv; `scripts/install_launchd.sh` resuelve el binario real.
