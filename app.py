import streamlit as st
import json
import zipfile
import io
import base64
from PIL import Image
import os

# --- DESIGN & BRANDING ---
st.set_page_config(page_title="ZackBerry Converter", page_icon="💎", layout="wide")

# Custom CSS for the Glowing Blue Background and Neon UI
st.markdown("""
    <style>
    /* Main background with a deep blue glow */
    .stApp {
        background: radial-gradient(circle, #001d3d 0%, #000814 100%);
        color: white;
    }
    
    /* Glowing Title */
    h1 {
        color: #00d4ff !important;
        text-shadow: 0 0 10px #00d4ff, 0 0 20px #00d4ff, 0 0 40px #00d4ff;
        text-align: center;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 2px;
    }

    /* File Uploader styling */
    .stFileUploader section {
        background-color: rgba(0, 29, 61, 0.5) !important;
        border: 2px dashed #00d4ff !important;
        border-radius: 15px;
    }

    /* Glowing Button */
    .stButton>button {
        background-color: #003566 !important;
        color: #00d4ff !important;
        border: 2px solid #00d4ff !important;
        border-radius: 20px;
        font-weight: bold;
        width: 100%;
        box-shadow: 0 0 10px #00d4ff;
        transition: 0.3s;
    }
    
    .stButton>button:hover {
        box-shadow: 0 0 25px #00d4ff, 0 0 50px #00d4ff;
        transform: scale(1.02);
        color: white !important;
        border-color: white !important;
    }

    /* Download button specific glow */
    .stDownloadButton>button {
        background: linear-gradient(45deg, #0077b6, #00d4ff) !important;
        color: white !important;
        border: none !important;
        box-shadow: 0 0 15px #00d4ff;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("ZackBerry Converter")

# --- CONVERTER LOGIC (UNCHANGED) ---
def process_bbmodel(file_obj):
    filename_base = os.path.splitext(file_obj.name)[0]
    bb_data = json.load(file_obj)
    
    # 1. FIXING BINDING BONES STRUCTURE
    primary_tex = "default"
    if 'textures' in bb_data and len(bb_data['textures']) > 0:
        primary_tex = bb_data['textures'][0].get('name', 'default').replace('.png', '')

    model_config = {
        "head_rotation": True,
        "material": "entity_alphatest_change_color_one_sided",
        "blend_transition": True,
        "per_texture_uv_size": {},
        "binding_bones": { primary_tex: [] }, # Must be a list under the texture name
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
                
                # Correction for Bedrock axis
                if 'rotation' in node:
                    bone["rotation"] = [node['rotation'][0], -node['rotation'][1], -node['rotation'][2]]

                for child in node.get('children', []):
                    if isinstance(child, str) and child in elements:
                        c = elements[child]
                        size = [round(c['to'][0]-c['from'][0], 4), round(c['to'][1]-c['from'][1], 4), round(c['to'][2]-c['from'][2], 4)]
                        # UV FIX
                        uv_origin = c.get('uv_offset', [0, 0])
                        bone["cubes"].append({"origin": c['from'], "size": size, "uv": uv_origin})
                    elif isinstance(child, dict):
                        bones.extend(compile_bones([child]))
                bones.append(bone)
        return bones

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_f:
        path = f"{filename_base}/"
        
        # Texture Base64 Extraction
        for tex in bb_data.get('textures', []):
            t_name = tex.get('name', 'texture').replace('.png', '')
            source = tex.get('source', '')
            if "," in source:
                img_data = base64.b64decode(source.split(",")[1])
                zip_f.writestr(f"{path}{t_name}.png", img_data)
                img = Image.open(io.BytesIO(img_data))
                model_config["per_texture_uv_size"][t_name] = [img.width, img.height]

        # Geometry Identifier Correction
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
        # Animations (Cleaned)
        anis = {a.get('name'): {"loop": True, "bones": a.get('bones', {})} for a in bb_data.get('animations', [])}
        zip_f.writestr(f"{path}{filename_base}.animation.json", json.dumps({"format_version":"1.8.0", "animations":anis}, indent=4))
        zip_f.writestr(f"{path}config.json", json.dumps(model_config, indent=4))

    return filename_base, zip_buffer.getvalue()

# --- APP INTERFACE ---
uploaded = st.file_uploader("Upload .bbmodel files", type=['bbmodel'], accept_multiple_files=True)
if uploaded:
    if st.button(f"🚀 CONVERT {len(uploaded)} MODELS"):
        master_zip = io.BytesIO()
        with zipfile.ZipFile(master_zip, "w") as master:
            for f in uploaded:
                name, data = process_bbmodel(f)
                master.writestr(f"{name}.zip", data)
        st.download_button("📥 Download ZackBerry Pack", master_zip.getvalue(), "ZackBerry_DeepFix.zip")
