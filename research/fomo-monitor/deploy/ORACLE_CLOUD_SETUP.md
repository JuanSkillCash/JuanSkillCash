# Desplegar live_monitor.py en una VM gratis de Oracle Cloud (Always Free)

Esta guía te deja `live_monitor.py` corriendo 24/7 en una máquina virtual
que **no depende de tu compu empresarial ni de la de un amigo**, sin costo
(el nivel "Always Free" de Oracle Cloud no vence — no es una prueba de 30
días). No requiere tarjeta de crédito recurrente; la piden solo para
verificar identidad al crear la cuenta.

**Nada de esto sube ninguna clave privada ni credencial a la VM.**
`live_monitor.py` sigue siendo solo lectura: la VM solo va a hacer
llamadas RPC públicas salientes hacia Solana y Robinhood Chain.

> Nota: la interfaz de Oracle Cloud cambia de tanto en tanto — si algún
> nombre de botón/menú no coincide exactamente, buscá el equivalente más
> cercano; el concepto (crear una VM "Always Free", abrirle SSH, correr un
> script) no cambia.

## 1. Crear la cuenta

1. Andá a la señal-up de Oracle Cloud Free Tier (buscá "Oracle Cloud Free
   Tier" en Google si no tenés el link a mano) y creá una cuenta.
2. Elegí una región cercana a vos (una vez elegida, no se puede cambiar
   fácilmente para los recursos "Always Free").
3. Te van a pedir una tarjeta para verificar identidad — es normal, no te
   cobra mientras te quedes dentro de los límites "Always Free".

## 2. Crear la VM (Compute Instance)

1. En el menú, andá a **Compute → Instances → Create Instance**.
2. Nombre: por ejemplo `fomo-live-monitor`.
3. **Imagen**: Ubuntu (la versión LTS más reciente disponible).
4. **Shape (tipo de maquina)**: elegí una marcada **"Always Free eligible"**
   — normalmente `VM.Standard.E2.1.Micro` (AMD, 1GB RAM) o una
   `VM.Standard.A1.Flex` (ARM/Ampere, podés asignarle 1 OCPU / 6GB RAM y
   sigue siendo gratis). Cualquiera de las dos alcanza de sobra para este
   script (no hace cálculos pesados, solo espera eventos de red).
5. **Claves SSH**: dejá que Oracle genere el par de claves y **descargá la
   clave privada** (archivo `.key` o `.pem`) — la vas a necesitar para
   conectarte. Guardala en un lugar seguro de tu compu (esto es la llave
   para entrar a TU VM, no tiene nada que ver con wallets ni con el
   proyecto).
6. Dejá el resto de las opciones por defecto y creá la instancia.
7. Cuando el estado pase a **"Running"**, copiá la **IP pública** que te
   muestra.

Si te aparece un error de "Out of host capacity" con la shape Ampere A1,
es un problema conocido y frecuente en Oracle (esa capacidad se agota
seguido) — probá de nuevo en otro momento, o cambiá a
`VM.Standard.E2.1.Micro`, que casi siempre tiene disponibilidad.

## 3. Conectarte por SSH

Desde tu compu (funciona igual en la terminal de Windows con
`ssh` si tenés Git Bash/PowerShell moderno, Mac o Linux):

```bash
chmod 400 /ruta/a/tu-clave.key
ssh -i /ruta/a/tu-clave.key ubuntu@<IP_PUBLICA_DE_LA_VM>
```

(El usuario por defecto en las imágenes Ubuntu de Oracle es `ubuntu`.)

## 4. Instalar dependencias en la VM

Ya conectado por SSH, en la VM:

```bash
sudo apt update && sudo apt install -y python3 python3-pip python3-venv git
```

## 5. Traer el proyecto a la VM

Opción simple (clonar el repo directamente, si es público o tenés acceso):

```bash
git clone https://github.com/JuanSkillCash/JuanSkillCash.git
cd JuanSkillCash/research/fomo-monitor
```

Si el repo es privado y no tenés credenciales de git configuradas en la
VM, la alternativa es copiar la carpeta `research/fomo-monitor` desde tu
compu con `scp`:

```bash
# desde TU COMPU, no desde la VM:
scp -i /ruta/a/tu-clave.key -r research/fomo-monitor ubuntu@<IP_PUBLICA_DE_LA_VM>:~/fomo-monitor
```

## 6. Instalar la única dependencia de Python del proyecto

```bash
pip3 install --user websockets
```

## 7. Poner tus wallets

En la VM, editá `wallets.txt` (con `nano wallets.txt` o `vi wallets.txt`)
y pegá tus ~10 wallets reales, formato `CHAIN,DIRECCION` (ver
`live_monitor.py` y el propio `wallets.txt` para el detalle):

```
SOLANA,7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU
ROBINHOOD,0x1234567890abcdef1234567890abcdef12345678
...
```

## 8. Probarlo primero en primer plano (unos segundos)

```bash
python3 live_monitor.py wallets.txt
```

Deberías ver el banner de arranque ("=== live_monitor.py — PRUEBA LIVE
FINAL ===", la lista de wallets, "Esperando operaciones NUEVAS..."). Si
ves eso y no un error, andá bien — cortalo con Ctrl+C y pasá al paso
siguiente para dejarlo corriendo de forma permanente.

## 9. Dejarlo corriendo 24/7 de verdad (systemd)

Esto hace que el monitor arranque solo si la VM se reinicia, y siga
corriendo aunque cierres la sesión SSH — la forma correcta de "dejarlo
corriendo" sin depender de que la terminal quede abierta.

1. Copiá el archivo de ejemplo `deploy/live-monitor.service` (incluido en
   este mismo repo) a systemd, ajustando las rutas si tu usuario o la
   ubicación del proyecto son distintos a los del ejemplo:

   ```bash
   sudo cp deploy/live-monitor.service /etc/systemd/system/live-monitor.service
   sudo nano /etc/systemd/system/live-monitor.service   # ajustar User= y WorkingDirectory= si hace falta
   sudo systemctl daemon-reload
   sudo systemctl enable --now live-monitor
   ```

2. Ver que esté corriendo y ver el log en vivo:

   ```bash
   sudo systemctl status live-monitor
   journalctl -u live-monitor -f
   ```

3. Para pararlo o reiniciarlo:

   ```bash
   sudo systemctl stop live-monitor
   sudo systemctl restart live-monitor
   ```

## 10. Ver las operaciones detectadas

El archivo `detected_trades.jsonl` va a ir creciendo en
`~/JuanSkillCash/research/fomo-monitor/` (o donde hayas puesto el
proyecto) cada vez que el sistema detecte una operación real. Para verlo
en vivo desde la VM:

```bash
tail -f detected_trades.jsonl
```

Para traerte ese archivo a tu compu cuando quieras revisarlo con calma:

```bash
# desde TU COMPU:
scp -i /ruta/a/tu-clave.key ubuntu@<IP_PUBLICA_DE_LA_VM>:~/JuanSkillCash/research/fomo-monitor/detected_trades.jsonl .
```

## Notas de seguridad y costos

- No hace falta abrir ningún puerto entrante en el firewall de la VM: el
  script solo hace conexiones **salientes** (a los RPC públicos de Solana
  y Robinhood Chain) — el firewall por defecto de Oracle ya permite salida
  sin cambios.
- Nunca subas ninguna clave privada de wallet a esta VM — el proyecto
  entero (`live_monitor.py`, los parsers, los adapters) está diseñado para
  no pedir ni necesitar ninguna.
- Los recursos "Always Free" de Oracle Cloud, dentro de sus límites
  (1 shape Ampere A1 con hasta 4 OCPU/24GB repartidos entre instancias, o
  2 `VM.Standard.E2.1.Micro`), no vencen y no generan cargo. Este script
  usa una fracción mínima de esos recursos.
