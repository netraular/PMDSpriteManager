# exportar_assets_comunes.py

from pathlib import Path
import shutil # Módulo para operaciones de archivos de alto nivel (copiar, borrar carpetas)

def procesar_y_exportar_animaciones():
    """
    Busca animaciones .json comunes a todos los personajes y genera una carpeta 'output'
    con los assets correspondientes (JSONs y sprites PNGs únicos).
    """
    carpeta_principal = Path.cwd()
    print(f"Analizando la estructura de carpetas en: {carpeta_principal}\n")

    # --- PARTE 1: Encontrar las animaciones comunes (lógica del script anterior) ---

    animaciones_por_personaje = {}
    carpetas_personajes = [d for d in carpeta_principal.iterdir() if d.is_dir() and not d.name.startswith(('.', 'output'))]

    if not carpetas_personajes:
        print("Error: No se encontraron subcarpetas de personajes en el directorio actual.")
        return

    for carpeta_personaje in carpetas_personajes:
        ruta_animation_data = carpeta_personaje / "AnimationData"
        if not ruta_animation_data.is_dir():
            continue
        
        nombres_animaciones = {f.name for f in ruta_animation_data.rglob('*.json')}
        if nombres_animaciones:
            animaciones_por_personaje[carpeta_personaje.name] = nombres_animaciones
            print(f"-> Personaje '{carpeta_personaje.name}' encontrado con {len(nombres_animaciones)} animaciones.")
        else:
             animaciones_por_personaje[carpeta_personaje.name] = set()

    if not animaciones_por_personaje:
        print("\nNo se encontraron personajes con carpetas 'AnimationData' válidas.")
        return

    lista_de_conjuntos = list(animaciones_por_personaje.values())
    animaciones_comunes = lista_de_conjuntos[0].copy()
    for siguiente_conjunto in lista_de_conjuntos[1:]:
        animaciones_comunes.intersection_update(siguiente_conjunto)

    if not animaciones_comunes:
        print("\n❌ No se encontró ninguna animación .json que sea común a todos los personajes. Proceso finalizado.")
        return
        
    print("\n-----------------------------------------------------")
    print("✅ Animaciones .json comunes encontradas:")
    for nombre_archivo in sorted(list(animaciones_comunes)):
        print(f"   - {nombre_archivo}")
    print("-----------------------------------------------------\n")

    # --- PARTE 2: Crear la estructura de salida y copiar los archivos ---

    print("Iniciando proceso de exportación...")
    
    # Crear o limpiar la carpeta de salida 'output'
    output_dir = carpeta_principal / "output"
    if output_dir.exists():
        print(f"Borrando carpeta 'output' existente para una exportación limpia...")
        shutil.rmtree(output_dir)
    output_dir.mkdir()

    # Iterar sobre cada personaje para procesar sus archivos
    for carpeta_personaje in carpetas_personajes:
        nombre_personaje = carpeta_personaje.name
        print(f"\n--- Procesando personaje: {nombre_personaje} ---")

        ruta_animation_data_origen = carpeta_personaje / "AnimationData"
        if not ruta_animation_data_origen.is_dir():
            print(f"Advertencia: El personaje '{nombre_personaje}' no tiene 'AnimationData'. Se omite.")
            continue

        # Crear carpetas de destino para este personaje
        output_personaje_dir = output_dir / nombre_personaje
        output_personaje_dir.mkdir()
        output_sprites_dir = output_personaje_dir / "Sprites"
        output_sprites_dir.mkdir()
        
        # Conjunto para llevar el registro de los PNGs ya copiados y evitar duplicados
        nombres_png_copiados = set()

        # Iterar sobre cada JSON común para copiarlo y buscar sus sprites
        for nombre_json in sorted(list(animaciones_comunes)):
            # 1. Copiar el archivo JSON
            try:
                # Buscamos la ruta completa del json original
                ruta_json_origen = next(ruta_animation_data_origen.rglob(nombre_json))
                ruta_json_destino = output_personaje_dir / nombre_json
                shutil.copy2(ruta_json_origen, ruta_json_destino)
                print(f"  ✅ Copiado JSON: {nombre_json}")
            except StopIteration:
                print(f"  ❌ Error: No se pudo encontrar el archivo '{nombre_json}' para '{nombre_personaje}'.")
                continue

            # 2. Derivar nombre de animación y copiar los sprites PNG
            nombre_animacion = nombre_json.removesuffix("-AnimData.json")
            ruta_sprites_origen = ruta_animation_data_origen / nombre_animacion
            
            if not ruta_sprites_origen.is_dir():
                print(f"  - Advertencia: No se encontró la carpeta de sprites '{nombre_animacion}' para este JSON.")
                continue

            print(f"  - Buscando sprites en: '{ruta_sprites_origen.relative_to(carpeta_principal)}'")
            pngs_encontrados = list(ruta_sprites_origen.glob('*.png'))
            
            if not pngs_encontrados:
                print("    - No se encontraron archivos .png en esta carpeta.")
                continue

            for png_origen in pngs_encontrados:
                if png_origen.name not in nombres_png_copiados:
                    # Si el nombre del archivo no ha sido copiado antes, lo copiamos
                    shutil.copy2(png_origen, output_sprites_dir)
                    nombres_png_copiados.add(png_origen.name)
                else:
                    # Si ya existe, lo omitimos
                    print(f"    - Omitiendo (nombre de archivo duplicado): {png_origen.name}")

    print("\n-----------------------------------------------------")
    print(f"✅ Proceso completado. Los archivos se han generado en la carpeta: {output_dir}")
    print("-----------------------------------------------------")

if __name__ == "__main__":
    procesar_y_exportar_animaciones()