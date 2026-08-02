# Casino Web Scraper & PostgreSQL Storage

Este proyecto permite extraer y registrar en una base de datos **PostgreSQL** (con respaldo local SQLite) el historial de giros (`#last100Spins`), datos del marcador actual (`hash current`), número de jugadores activos (`playersActive`), monto ingresado/apostado (`Monto`) y dinero retirado/ganado (`playersCashOut`) del juego en línea.

## Configuración de Entorno (`.env`)

El archivo **[.env](file:///c:/Users/ADRIAN/Desktop/TRABAJO/casino/.env)** almacena las credenciales de conexión a PostgreSQL. Puedes modificarlo con tus credenciales de producción o locales:

```env
# Tipo de base de datos: 'postgres' o 'sqlite'
DB_TYPE=postgres

# Credenciales de PostgreSQL
DB_HOST=localhost
DB_PORT=5432
DB_NAME=casino_db
DB_USER=postgres
DB_PASSWORD=tu_contraseña_aqui

# Opcional: URL completa de conexión PostgreSQL
# DATABASE_URL=postgresql://usuario:password@host:5432/casino_db
```

*Nota: El archivo `.env` está en `.gitignore` para no subir tus contraseñas al repositorio git.*

## Archivos Creados

1. **[.env](file:///c:/Users/ADRIAN/Desktop/TRABAJO/casino/.env)**: Archivo de variables de entorno con credenciales de la base de datos.
2. **[.env.example](file:///c:/Users/ADRIAN/Desktop/TRABAJO/casino/.env.example)**: Plantilla de ejemplo para repositorios Git.
3. **[.gitignore](file:///c:/Users/ADRIAN/Desktop/TRABAJO/casino/.gitignore)**: Configuración para omitir credenciales y bases de datos locales.
4. **[database.py](file:///c:/Users/ADRIAN/Desktop/TRABAJO/casino/database.py)**: Conector multi-motor a **PostgreSQL** utilizando `psycopg2` y comandos SQL `ON CONFLICT ... DO UPDATE` para evitar duplicados por Hash.
5. **[scraper.py](file:///c:/Users/ADRIAN/Desktop/TRABAJO/casino/scraper.py)**: Script principal para web scraping en vivo mostrando el HASH y enviando métricas a la base de datos.
6. **[view_data.py](file:///c:/Users/ADRIAN/Desktop/TRABAJO/casino/view_data.py)**: Herramienta para consultar los datos almacenados en PostgreSQL o SQLite.
7. **[clear_data.py](file:///c:/Users/ADRIAN/Desktop/TRABAJO/casino/clear_data.py)**: Script utilitario para vaciar las tablas.

## Comandos

- **Ejecutar Scraper en Vivo**:
  ```bash
  python scraper.py --live
  ```
- **Consultar los Datos Guardados**:
  ```bash
  python view_data.py
  ```
- **Borrar los Datos de la Base de Datos**:
  ```bash
  python clear_data.py
  ```
