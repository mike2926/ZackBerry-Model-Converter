import streamlit as st
import json
import zipfile
import io
import base64
from PIL import Image
import os

# --- BRANDING & GLOW UI ---
st.set_page_config(page_title="ZackBerry Converter", page_icon="💎", layout="wide")

# Custom CSS for the "Glow" effect and neutral dark theme
st.markdown("""
    <style>
    /* Dark neutral background */
    .stApp { background-color: #0e1117; }
    
    /* Glowing Title */
    h1 { 
        color: #ffffff !important; 
        text-align: center; 
        font-weight: 800;
        text-shadow: 0 0 10px #fff, 0 0 20px #fff, 0 0 40px #ffffff;
        margin-bottom: 50px;
    }
    
    /* Glowing Neon Button */
    .stButton>button {
        background-color: #1a1a1a !important;
        color: #ffffff !important;
        border: 2px solid #ffffff !important;
        border-radius: 10px;
        font-weight: bold;
        transition: 0.3s;
        box-shadow: 0 0 5px #fff, 0 0 10px #fff;
    }
    
    .stButton>button:hover {
        box-shadow: 0 0 20px #fff, 0 0 40px #fff;
        transform: scale(1.02);
    }

    /* Standard text colors */
    .stMarkdown, label, p { color: #ffffff !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("ZackBerry Converter")

def process_bbmodel(file_obj):
    filename_base = os.path.splitext(file_obj.name)[0]
    bb_data = json.load(file_obj)
    
    # Identify primary texture
    primary_tex = "default"
    if 'textures' in bb_data and len(bb_data['textures']) > 0:
        primary_tex = bb_data['textures'][0].get('name', 'default').replace('.png', '')

    model_config = {
        "head_rotation": True,
        "material": "entity_alphatest_change_color_one_sided",
        "blend_transition": True,
        "per_texture_uv_size": {},
        "binding_bones": { primary_tex: [] }, 
        "anim_textures": {}
    }

    elements = {el['uuid']: el for el in bb_data.get('elements', [])}
    
    def compile_bones(nodes):
        bones = []
        for node in nodes:
            if isinstance(node, dict) and 'name' in node:
                bone_name = node['name']
                model_config["binding_bones"][primary_tex].append(bone_name)
                
                bone = {"name": bone_name, "pivot": node.get('origin', [0, 0, 0]), "cubes": []}
                if 'rotation' in node:
                    bone["rotation"] = [node['rotation'][0], -node['rotation'][1], -node['rotation'][2]]

                for child in node.get('children', []):
                    if isinstance(child, str) and child in elements:
                        c = elements[child]
                        size = [round(c['to'][0]-c['from'][0], 4), round(c['to'][1]-c['from'][1], 4), round(c['to'][2]-c['from'][2], 4)]
                        # Get North face for Box UV origin
                        uv_origin = [0, 0]
                        if 'faces' in c and 'north' in c['faces']:
                            uv_origin = c['faces']['north'].get('uv', [0, 0])[:2]
                        bone["cubes"].append({"origin": c['from'], "size": size, "uv": uv_origin})
                    elif isinstance(child, dict):
                        bones.extend(compile_bones([child]))
                bones.append(bone)
        return bones

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_f:
        path = f"{filename_base}/"
        
        # Textures
        for tex in bb_data.get('textures', []):
            t_name = tex.get('name', 'texture').replace('.png', '')
            source = tex.get('source', '')
            if "," in source:
                img_data = base64.b64decode(source.split(",")[1])
                img = Image.open(io.BytesIO(img_data))
                model_config["per_texture_uv_size"][t_name] = [img.width, img.height]
                zip_f.writestr(f"{path}{t_name}.png", img_data)

        # Geometry
        geo = {
            "format_version": "1.12.0",
            "minecraft:geometry": [{
                "description": {
                    "identifier": f"geometry.{filename_base}",
                    "texture_width": bb_data['resolution']['width'], 
                    "texture_height": bb_data['resolution']['height'],
                    "visible_bounds_width": 10, "visible_bounds_height": 10,
                    "visible_bounds_offset": [0, 5, 0]
                },
                "bones": compile_bones(bb_data.get('outliner', []))
            }]
        }
        
        zip_f.writestr(f"{path}{filename_base}.geo.json", json.dumps(geo, indent=4))
        
        # Animations (Mapping clean format)
        anis = {}
        for a in bb_data.get('animations', []):
            anis[a.get('name')] = {
                "loop": True,
                "animation_length": a.get('length', 0),
                "bones": a.get('bones', {})
            }
            
        zip_f.writestr(f"{path}{filename_base}.animation.json", json.dumps({"format_version":"1.8.0", "animations":anis}, indent=4))
        zip_f.writestr(f"{path}config.json", json.dumps(model_config, indent=4))

    return filename_base, zip_buffer.getvalue()

# --- APP LAYOUT ---
files = st.file_uploader("Upload .bbmodel files", type=['bbmodel'], accept_multiple_files=True)

if files:
    if st.button(f"CONVERT {len(files)} MODELS"):
        master_zip = io.BytesIO()
        with zipfile.ZipFile(master_zip, "w") as master:
            for f in files:
                name, data = process_bbmodel(f)
                master.writestr(f"{name}.zip", data)
        
        st.download_button("Download", master_zip.getvalue(), "ZackBerry_Bundle.zip")



