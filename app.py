import streamlit as st
import json
import zipfile
import io
import base64
from PIL import Image
import os

# --- DESIGN: GLOWING BLUE NEON UI ---
st.set_page_config(page_title="ZackBerry Converter", page_icon="💎", layout="wide")

st.markdown("""
    <style>
    /* Glowing Blue Radial Background */
    .stApp {
        background: radial-gradient(circle at center, #001d3d 0%, #000814 100%);
        color: white;
    }
    
    /* Neon Glowing Title */
    h1 {
        color: #ffffff !important;
        text-align: center;
        font-weight: 800;
        text-shadow: 0 0 10px #00d4ff, 0 0 20px #00d4ff, 0 0.40px #00d4ff;
        text-transform: uppercase;
        letter-spacing: 3px;
        padding-top: 20px;
    }

    /* Glowing Custom Button */
    .stButton>button {
        background-color: #000814 !important;
        color: #00d4ff !important;
        border: 2px solid #00d4ff !important;
        border-radius: 12px;
        font-weight: bold;
        width: 100%;
        box-shadow: 0 0 15px rgba(0, 212, 255, 0.4);
        transition: 0.3s ease-in-out;
    }
    
    .stButton>button:hover {
        box-shadow: 0 0 30px #00d4ff;
        background-color: #00d4ff !important;
        color: #000814 !important;
        transform: translateY(-2px);
    }

    /* File Uploader Style */
    .stFileUploader section {
        background-color: rgba(0, 29, 61, 0.3) !important;
        border: 1px solid #00d4ff !important;
        border-radius: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("ZackBerry Converter")

# --- CONVERTER ENGINE (FIXED FOR BEDROCK VISIBILITY) ---
def process_bbmodel(file_obj):
    filename_base = os.path.splitext(file_obj.name)[0]
    bb_data = json.load(file_obj)
    
    # Identify the main texture to prevent invisible mapping
    primary_tex = "default"
    if 'textures' in bb_data and len(bb_data['textures']) > 0:
        primary_tex = bb_data['textures'][0].get('name', 'default').replace('.png', '')

    model_config = {
        "head_rotation": True,
        "material": "entity_alphatest_change_color_one_sided",
        "blend_transition": True,
        "per_texture_uv_size": {},
        "binding_bones": { primary_tex: [] }, # Grouping bones in a list is required
        "anim_textures": {}
    }

    elements = {el['uuid']: el for el in bb_data.get('elements', [])}
    
    def compile_bones(nodes):
        bones = []
        for node in nodes:
            if isinstance(node, dict) and 'name' in node:
                bone_name = node['name']
                # Correctly append bone to the list under the texture key
                model_config["binding_bones"][primary_tex].append(bone_name)
                
                bone = {"name": bone_name, "pivot": node.get('origin', [0, 0, 0]), "cubes": []}
                if 'rotation' in node:
                    bone["rotation"] = [node['rotation'][0], -node['rotation'][1], -node['rotation'][2]]

                for child in node.get('children', []):
                    if isinstance(child, str) and child in elements:
                        c = elements[child]
                        size = [round(c['to'][0]-c['from'][0], 4), round(c['to'][1]-c['from'][1], 4), round(c['to'][2]-c['from'][2], 4)]
                        # UV Alignment Fix
                        uv_origin = c.get('uv_offset', [0, 0])
                        bone["cubes"].append({"origin": c['from'], "size": size, "uv": uv_origin})
                    elif isinstance(child, dict):
                        bones.extend(compile_bones([child]))
                bones.append(bone)
        return bones

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_f:
        path = f"{filename_base}/"
        
        # Base64 Textures
        for tex in bb_data.get('textures', []):
            t_name = tex.get('name', 'texture').replace('.png', '')
            source = tex.get('source', '')
            if "," in source:
                img_data = base64.b64decode(source.split(",")[1])
                zip_f.writestr(f"{path}{t_name}.png", img_data)
                img = Image.open(io.BytesIO(img_data))
                model_config["per_texture_uv_size"][t_name] = [img.width, img.height]

        # Sync Geometry ID with Filename
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
        # Animation Stitching
        anis = {a.get('name'): {"loop": True, "bones": a.get('bones', {})} for a in bb_data.get('animations', [])}
        zip_f.writestr(f"{path}{filename_base}.animation.json", json.dumps({"format_version":"1.8.0", "animations":anis}, indent=4))
        zip_f.writestr(f"{path}config.json", json.dumps(model_config, indent=4))

    return filename_base, zip_buffer.getvalue()

# --- APP LAYOUT ---
uploaded = st.file_uploader("Upload .bbmodel", type=['bbmodel'], accept_multiple_files=True)
if uploaded:
    if st.button(f"🚀 CONVERT {len(uploaded)} MODELS"):
        master_zip = io.BytesIO()
        with zipfile.ZipFile(master_zip, "w") as master:
            for f in uploaded:
                name, data = process_bbmodel(f)
                master.writestr(f"{name}.zip", data)
        st.download_button("📥 Download ZackBerry Pack", master_zip.getvalue(), "ZackBerry_DeepFix.zip")

