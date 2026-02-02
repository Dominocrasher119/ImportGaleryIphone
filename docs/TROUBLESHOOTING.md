# Troubleshooting

## Español
**El iPhone no aparece**
- Usa un cable de datos y prueba otro puerto USB.
- Desbloquea el iPhone y acepta “Confiar en este ordenador”.
- Reinicia el servicio **Dispositivos Portátiles (WPD)** en Windows.
- Si tienes iTunes instalado, reinicia **Apple Mobile Device Service**.
- Cierra y vuelve a abrir iImport, o reinicia el PC.

**El escaneo falla**
- Desbloquea el iPhone y mantén la pantalla encendida durante el escaneo.
- Repite el escaneo. Si persiste, revisa `_cache\scan_logs\` junto al `.exe`.

**Conversión compatible no funciona**
- Asegúrate de tener `tools\ffmpeg.exe` y `tools\exiftool.exe` junto al `.exe`.
- Algunos builds de ffmpeg no soportan HEIC/HEIF. Prueba otra versión.
- El detalle del error queda en el log de importación.

**Mensaje “Dispositivo desconectado”**
- Reconecta el iPhone y repite la importación.
- Evita desconectar el cable durante la copia.

## Català
**L’iPhone no apareix**
- Fes servir un cable de dades i prova un altre port USB.
- Desbloqueja l’iPhone i accepta “Confia en aquest ordinador”.
- Reinicia el servei **Dispositius Portàtils (WPD)** a Windows.
- Si tens iTunes instal·lat, reinicia **Apple Mobile Device Service**.
- Tanca i torna a obrir iImport, o reinicia el PC.

**L’escaneig falla**
- Desbloqueja l’iPhone i mantén la pantalla encesa durant l’escaneig.
- Torna a escanejar. Si continua, revisa `_cache\scan_logs\` al costat del `.exe`.

**La conversió compatible no funciona**
- Assegura’t de tenir `tools\ffmpeg.exe` i `tools\exiftool.exe` al costat del `.exe`.
- Alguns builds de ffmpeg no suporten HEIC/HEIF. Prova una altra versió.
- El detall de l’error queda al log d’importació.

**Missatge “Dispositiu desconnectat”**
- Torna a connectar l’iPhone i repeteix la importació.
- Evita desconnectar el cable durant la còpia.
