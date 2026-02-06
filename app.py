import streamlit as st
import json
import zipfile
import io
import base64
from PIL import Image
import os

# --- BRANDING ---
st.set_page_config(page_title="ZackBerry Converter", page_icon="💎", layout="wide")
st.markdown("""
    <style>
    .stApp { background: radial-gradient(circle, #001d3d 0%, #000814 100%); }
    h1 { color: #00d4ff !important; text-shadow: 0 0 15px #00d4ff; text-align: center; font-weight: 800; }
    .stButton>button { background-color: #003566 !important; color: #00d4ff !important; border: 2px solid #00d4ff !important; width: 100%; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.title("💎 ZackBerry Converter")

def process_bbmodel(file_obj):
    filename_base = os.path.splitext(file_obj.name)[0]
    bb_data = json.load(file_obj)
    
    # 1. RESOLUTION & METADATA
    res_x = bb_data.get('resolution', {}).get('width', 16)
    res_y = bb_data.get('resolution', {}).get('height', 16)
    
    model_config = {
        "head_rotation": True,
        "material": "entity_alphatest_change_color_one_sided",
        "blend_transition": True,
        "per_texture_uv_size": {},
        "binding_bones": {},
        "anim_textures": {}
    }

    # 2. BONE & CUBE COMPILATION (Crucial for GME)
    element_map = {el['uuid']: el for el in bb_data.get('elements', []) if 'uuid' in el}
    bedrock_bones = []
    
    def compile_bones(nodes):
        for node in nodes:
            if isinstance(node, dict) and 'name' in node:
                bone_name = node['name']
                model_config["binding_bones"][bone_name] = bone_name
                
                bone = {
                    "name": bone_name,
                    "pivot": node.get('origin', [0, 0, 0]),
                    "cubes": []
                }
                if 'rotation' in node:
                    bone["rotation"] = [node['rotation'][0], -node['rotation'][1], -node['rotation'][2]]

                for child in node.get('children', []):
                    if isinstance(child, str) and child in element_map:
                        c = element_map[child]
                        size = [round(c['to'][0]-c['from'][0],4), round(c['to'][1]-c['from'][1],4), round(c['to'][2]-c['from'][2],4)]
                        cube = {"origin": c['from'], "size": size, "uv": c.get('uv_offset', [0,0])}
                        if 'rotation' in c:
                            cube["rotation"] = [c['rotation'][0], -c['rotation'][1], -c['rotation'][2]]
                            cube["pivot"] = c.get('origin', [0, 0, 0])
                        bone["cubes"].append(cube)
                    elif isinstance(child, dict):
                        compile_bones([child])
                bedrock_bones.append(bone)

    compile_bones(bb_data.get('outliner', []))

    # 3. COMPILING ANIMATIONS (This adds weight to the file)
    animations = {}
    if 'animations' in bb_data:
        for ani in bb_data['animations']:
            ani_name = ani.get('name', 'animation')
            # Stripping internal Blockbench data for Bedrock compatibility
            animations[ani_name] = {
                "loop": ani.get('loop', 'loop'),
                "animation_length": ani.get('length', 0),
                "bones": ani.get('bones', {})
            }

    # 4. ZIP PACKING WITH TEXTURE EXTRACTION
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_f:
        folder = f"{filename_base}/"
        
        # Texture Processing
        if 'textures' in bb_data:
            for tex in bb_data['textures']:
                t_name = tex.get('name', 'texture').replace('.png', '')
                source = tex.get('source', '')
                if "," in source:
                    img_data = base64.b64decode(source.split(",")[1])
                    img = Image.open(io.BytesIO(img_data))
                    model_config["per_texture_uv_size"][t_name] = [img.width, img.height]
                    zip_f.writestr(f"{folder}{t_name}.png", img_data)

        # Geometry Identifier
        geo = {
            "format_version": "1.12.0",
            "minecraft:geometry": [{
                "description": {
                    "identifier": f"geometry.{filename_base}",
                    "texture_width": res_x, "texture_height": res_y,
                    "visible_bounds_width": 10, "visible_bounds_height": 10,
                    "visible_bounds_offset": [0, 5, 0]
                },
                "bones": bedrock_bones
            }]
        }
        
        zip_f.writestr(f"{folder}{filename_base}.geo.json", json.dumps(geo, indent=4))
        zip_f.writestr(f"{folder}{filename_base}.animation.json", json.dumps({"format_version":"1.8.0","animations":animations}, indent=4))
        zip_f.writestr(f"{folder}config.json", json.dumps(model_config, indent=4))

    return filename_base, zip_buffer.getvalue()

files = st.file_uploader("Upload .bbmodel files", type=['bbmodel'], accept_multiple_files=True)

if files:
    if st.button(f"🚀 CONVERT {len(files)} MODELS"):
        master_zip = io.BytesIO()
        with zipfile.ZipFile(master_zip, "w") as master:
            for f in files:
                name, data = process_bbmodel(f)
                master.writestr(f"{name}.zip", data)
        st.download_button("📥 Download", master_zip.getvalue(), "ZackBerry_Bundle.zip")

