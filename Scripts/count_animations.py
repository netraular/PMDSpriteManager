import os
import xml.etree.ElementTree as ET
from collections import Counter # <-- 1. Importar Counter

def count_animation_names(search_path='.'):
    """
    Busca en el directorio especificado carpetas que contengan una subcarpeta 'Animations'
    con un archivo 'AnimData.xml' y cuenta la frecuencia de cada nombre de animación.

    Args:
        search_path (str): La ruta del directorio donde comenzar la búsqueda. 
                           Por defecto es el directorio actual ('.').
    
    Returns:
        collections.Counter: Un objeto Counter con los nombres de las animaciones como claves
                             y su frecuencia como valores.
    """
    # 2. Usar Counter en lugar de set
    animation_counts = Counter()
    
    print(f"Buscando en el directorio: {os.path.abspath(search_path)}\n")

    # Listamos todos los elementos (archivos y carpetas) en el directorio de búsqueda
    for item_name in os.listdir(search_path):
        item_path = os.path.join(search_path, item_name)

        # Nos aseguramos de que sea una carpeta
        if os.path.isdir(item_path):
            # Construimos la ruta al posible archivo AnimData.xml
            anim_xml_path = os.path.join(item_path, 'Animations', 'AnimData.xml')

            # Comprobamos si el archivo existe en esa ruta
            if os.path.isfile(anim_xml_path):
                print(f"  -> Procesando archivo en: {anim_xml_path}")
                try:
                    # Parseamos el archivo XML
                    tree = ET.parse(anim_xml_path)
                    root = tree.getroot()
                    
                    # Buscamos todos los tags <Anim>
                    for anim_node in root.findall('.//Anims/Anim'):
                        name_node = anim_node.find('Name')
                        if name_node is not None and name_node.text:
                            name = name_node.text.strip()
                            # 3. Incrementar el contador para esta animación
                            animation_counts[name] += 1
                
                except ET.ParseError as e:
                    print(f"    [ERROR] No se pudo procesar el archivo XML '{anim_xml_path}': {e}")
                except Exception as e:
                    print(f"    [ERROR] Ocurrió un error inesperado al procesar '{anim_xml_path}': {e}")

    return animation_counts

# --- Ejecución del script ---
if __name__ == "__main__":
    # Llamamos a la función para que busque en el directorio actual
    counts = count_animation_names()

    print("\n--- RESULTADOS ---")
    if counts:
        print("Recuento de animaciones encontradas (de más a menos frecuente):")
        # 4. Usamos el método .most_common() de Counter para obtener una lista
        #    ordenada de tuplas (nombre, cantidad)
        for name, count in counts.most_common():
            # Añadimos lógica para singular/plural ("vez" vs "veces")
            veces_str = "vez" if count == 1 else "veces"
            print(f"- {name}: {count} {veces_str}")
    else:
        print("No se encontraron archivos 'AnimData.xml' en la estructura de carpetas esperada.")
        print("Asegúrate de ejecutar este script en el directorio correcto.")