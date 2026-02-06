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
    h1 { color: #00d4ff !important; text-shadow: 0 0 15px #00d4ff; text-align: center; }
    .stButton>button { background-color: #003566 !important; color: #00d4ff !important; border: 2px solid #00d4ff !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("💎 ZackBerry Ultimate Converter")

def process_bbmodel(file_obj):
    filename_base = os.path.splitext(file_obj.name)[0]
    bb_data = json.load(file_obj)
    
    # 1. UV RESOLUTION
    res_x = bb_data.get('resolution', {}).get('width', 16)
    res_y = bb_data.get('resolution', {}).get('height', 16)
    
    # 2. GME CONFIG INITIALIZATION
    # This matches the 'geyser_model_engine_packer.js' requirements
    model_config = {
        "head_rotation": True,
        "material": "entity_alphatest_change_color_one_sided",
        "blend_transition": True,
        "per_texture_uv_size": {},
        "binding_bones": {},
        "anim_textures": {}
    }

    element_map = {el['uuid']: el for el in bb_data.get('elements', []) if 'uuid' in el}
    bedrock_bones = []
    
    def compile_bones(nodes):
        for node in nodes:
            if isinstance(node, dict) and 'name' in node:
                bone_name = node['name']
                
                # BINDING BONES: Crucial for GeyserModelEngine to track movements
                model_config["binding_bones"][bone_name] = bone_name
                
                bone = {
                    "name": bone_name,
                    "pivot": node.get('origin', [0, 0, 0]),
                    "cubes": []
                }
                
                # Bedrock rotation inversion
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

    # 3. VISIBILITY BOX MATH (Prevents model vanishing)
    coords = []
    for el in bb_data.get('elements', []):
        coords.extend(el.get('from', []))
        coords.extend(el.get('to', []))
    max_reach = max([abs(x) for x in coords]) if coords else 16
    v_width = max(3, int(((max_reach + 8) * 2) / 16) + 1)

    # 4. PACKING
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_f:
        folder = f"{filename_base}/"
        
        # Textures
        if 'textures' in bb_data:
            for tex in bb_data['textures']:
                t_name = tex.get('name', 'texture').replace('.png', '')
                source = tex.get('source', '')
                if "," in source: source = source.split(",")[1]
                if source:
                    img_data = base64.b64decode(source)
                    img = Image.open(io.BytesIO(img_data))
                    model_config["per_texture_uv_size"][t_name] = [img.width, img.height]
                    zip_f.writestr(f"{folder}{t_name}.png", img_data)

        # Geometry
        geo = {
            "format_version": "1.12.0",
            "minecraft:geometry": [{
                "description": {
                    "identifier": f"geometry.{filename_base}",
                    "texture_width": res_x, "texture_height": res_y,
                    "visible_bounds_width": v_width, "visible_bounds_height": v_width,
                    "visible_bounds_offset": [0, v_width/2, 0]
                },
                "bones": bedrock_bones
            }]
        }
        zip_f.writestr(f"{folder}{filename_base}.geo.json", json.dumps(geo, indent=4))
        
        # Animations & Config
        zip_f.writestr(f"{folder}{filename_base}.animation.json", json.dumps({"format_version":"1.8.0","animations":{}}, indent=4))
        zip_f.writestr(f"{folder}config.json", json.dumps(model_config, indent=4))

    return filename_base, zip_buffer.getvalue()

uploaded_files = st.file_uploader("Upload .bbmodel files", type=['bbmodel'], accept_multiple_files=True)

if uploaded_files:
    if st.button(f"🚀 CONVERT {len(uploaded_files)} MODELS"):
        master_zip = io.BytesIO()
        with zipfile.ZipFile(master_zip, "w") as master:
            for f in uploaded_files:
                name, data = process_bbmodel(f)
                master.writestr(f"{name}.zip", data)
        st.download_button("📥 Download", master_zip.getvalue(), "ZackBerry_Bundle.zip")
