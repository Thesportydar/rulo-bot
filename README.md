# Rulo monitor

Monitorea el **rulo MEP → USDT → ARS** y avisa por Telegram cuando deja ganancia.

1. **Comprar** dólar MEP con pesos (Cocos, Fiwind, Plus Inversiones)
2. **Convertir** USD a USDT (Fiwind, Belo, Nexo, Ripio, Let'sBit, Decrypto, TiendaCrypto, SatoshiTango)
3. **Vender** USDT por pesos (Belo, Lemon, Cocos Crypto, Fiwind, Ripio, Nexo, Takenos, Let'sBit, Plus Crypto, Decrypto, TiendaCrypto, SatoshiTango)

Evalúa todas las combinaciones compra × conversión × venta y calcula:

```
costo por USDT = MEP (ask, ARS/USD) × tasa (ask, USD/USDT)
ganancia %     = venta (bid, ARS/USDT) / costo por USDT − 1
```

Las comisiones fijas de red (0,5–1 USDT) no se descuentan. Las comisiones porcentuales sí, porque
se usan `totalAsk`/`totalBid` cuando la fuente los informa.

Ejemplo de aviso:

```
🔥 Rulo abierto

1. 1,55% · MEP Cocos 1.550,00 → convertir en Fiwind 1,0400 → vender en Belo / Cocos Crypto 1.637,00
2. 1,36% · MEP Fiwind MEP 1.553,00 → convertir en Fiwind (sin transferir) 1,0400 → vender en Belo 1.637,00

Costo por USDT: 1.612,00 ARS
```

## Fuentes de precios

| Paso | Fuente | Endpoint | Campo |
|---|---|---|---|
| MEP por broker | [comparadolar](https://comparadolar.ar/llms.txt) | `/usd` | `ask` |
| USD → USDT | [CriptoYa](https://criptoya.com/api) | `/api/USDT/USD/{volumen}` | `totalAsk` |
| USDT → ARS | CriptoYa (Plus Crypto por comparadolar) | `/api/USDT/ARS/{volumen}` | `totalBid` |

Ninguna pide API key. CriptoYa ajusta el precio al volumen (`amount_usdt` en la config).

Limitaciones conocidas:

- comparadolar no informa timestamp para USD, y en CriptoYa `time` es la hora de consulta, no de la
  última actualización. Un precio congelado (ej. Fiwind en mantenimiento) no se detecta; por eso solo
  corre en horario de mercado.
- Se descartan a propósito: dólar oficial (regulaciones), P2P, y plataformas del exterior
  (Astropay, Xapo, Wallbit) porque no aceptan USD MEP.

## Configuración

Todo está en [`config.toml`](config.toml): plataformas de cada paso, umbrales, horario y frescura de
datos. Cada plataforma se declara así:

```toml
[[convert]]
name = "Fiwind"          # nombre en los avisos
platform = "fiwind"      # id propio; igual en compra y conversión = "sin transferir"
source = "criptoya"      # fuente de precios
slug = "fiwind"          # id del proveedor en esa fuente
pair = "USDT/USD"
```

| Umbral | Default | Qué hace |
|---|---|---|
| `open_pct` | 1,0 | avisa 🟢 cuando la mejor ruta llega a este % |
| `strong_pct` | 1,5 | el aviso sale con 🔥 |
| `improve_pct` | 0,3 | vuelve a avisar si mejora esta cantidad de puntos |
| `close_pct` | 0,8 | avisa ⚪ cerrado por debajo de esto (histéresis) |

Además avisa si hay 5 corridas seguidas sin datos. Una ruta abierta de un día anterior se descarta,
así el primer aviso de cada día es siempre de apertura.

## Uso local

Requiere Python 3.11+, sin dependencias.

```bash
cp .env.example .env            # TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
python3 -m rulo --dry-run       # tabla de rutas, sin avisar ni guardar estado
python3 -m rulo --test-notify   # mensaje de prueba a Telegram
python3 -m rulo --force         # una corrida real ignorando el horario
python3 -m unittest             # tests (sin red)
```

Sin token, los avisos salen por consola. Para correrlo en la Mac cada `interval_seconds`:
`scripts/install_launchd.sh` (y `scripts/install_launchd.sh uninstall` para sacarlo).

## Deploy en AWS

Producción corre en Lambda, disparada por EventBridge Scheduler cada 2 minutos, de lunes a viernes de
11 a 17 hora de Argentina. El estado va en DynamoDB y el token de Telegram en SSM. Todo entra en el
free tier o cuesta fracciones de centavo por mes.

```
EventBridge Scheduler ──▶ Lambda rulo-bot-dev ──▶ comparadolar / CriptoYa
                               │        │
                    DynamoDB state    SSM token ──▶ Telegram
```

El tfstate va a un bucket S3 de la cuenta mgmt. Los recursos se crean en la cuenta dev asumiendo
`TerraformExecutionRole`, que solo acepta el SSO `TerraformAdmin` (perfil `terraform-admin`).

`backend.conf` y `dev.tfvars` tienen IDs de cuentas y el chat id, así que no se versionan: se crean a
partir de los `.example`.

```bash
cd terraform
cp backend.conf.example backend.conf   # completar bucket y cuenta mgmt
cp dev.tfvars.example dev.tfvars       # completar cuenta dev y chat id
terraform init -backend-config=backend.conf
terraform apply -var-file=dev.tfvars

# el token se carga a mano para que no quede en el tfstate
aws --profile dev-admin ssm put-parameter --overwrite --type SecureString \
  --name /rulo-bot/dev/telegram-bot-token --value '<token>'
```

Operación:

```bash
# probar sin avisar
aws --profile dev-admin lambda invoke --function-name rulo-bot-dev \
  --cli-binary-format raw-in-base64-out --payload '{"args":["--dry-run"]}' \
  --log-type Tail out.json --query LogResult --output text | base64 -d

# logs
aws --profile dev-admin logs tail /aws/lambda/rulo-bot-dev --follow

# pausar / reanudar
terraform apply -var-file=dev.tfvars -var schedule_enabled=false
```

El evento de la Lambda acepta `{"args": [...]}` con los mismos flags que la CLI.
