from flask import Flask, render_template, request, redirect, send_file,  make_response, url_for
import io
import qrcode
from io import BytesIO
import base64
import datetime
import csv
from fpdf import FPDF
import os
import pandas as pd
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.io as pio
from datetime import datetime
from PIL import Image, ImageDraw
from flask_cas import CAS

app = Flask(__name__)

# Configuration de l'application Flask pour CAS
app.config['CAS_SERVER'] = 'https://thor.univ-evry.fr/cas'
app.config['CAS_AFTER_LOGIN'] = 'index'  # Page après connexion
app.config['SECRET_KEY'] = 'a1b2c3d4e5f67890123456789abcdef0' 

cas = CAS(app)

@app.route('/login')
def login():
    return redirect(url_for('cas.login'))

@app.route('/logout')
def logout():
    return redirect(url_for('cas.logout')) 

@app.route('/download_filtered_csv', methods=['POST'])
def download_filtered_csv():
    if not cas.username:  # Vérifie si l'utilisateur est connecté
        return redirect(url_for('login'))  # Redirige vers la page de connexion CAS

    df = load_log_data()

    # Appliquer les filtres pour les lieux, les sites web, et les dates
    selected_places = request.form.getlist('places')
    selected_websites = request.form.getlist('websites')

    if selected_places:
        df = df[df['Place'].isin(selected_places)]
    if selected_websites:
        df = df[df['Website'].isin(selected_websites)]

    # Sélectionner uniquement les colonnes "Website", "Scan Time", "Place"
    df_filtered = df[['Website', 'Scan Time', 'Place']]

    # Générer le CSV
    response = make_response(df_filtered.to_csv(index=False))
    response.headers["Content-Disposition"] = "attachment; filename=tableau_filtre.csv"
    response.headers["Content-Type"] = "text/csv"

    return response

@app.route('/download_filtered_excel', methods=['POST'])
def download_filtered_excel():
    if not cas.username:  # Vérifie si l'utilisateur est connecté
        return redirect(url_for('login'))  # Redirige vers la page de connexion CAS

    df = load_log_data()

    # Appliquer les filtres pour les lieux et les sites web
    selected_places = request.form.getlist('places')
    selected_websites = request.form.getlist('websites')

    if selected_places:
        df = df[df['Place'].isin(selected_places)]
    if selected_websites:
        df = df[df['Website'].isin(selected_websites)]

    # Sélectionner uniquement les colonnes "Website", "Scan Time", "Place"
    df_filtered = df[['Website', 'Scan Time', 'Place']]

    # Créer le fichier Excel
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_filtered.to_excel(writer, index=False)

    output.seek(0)
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=tableau_filtre.xlsx"
    response.headers["Content-Type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    return response

# Charger les logs du fichier CSV
def load_log_data():
    if not cas.username:  # Vérifie si l'utilisateur est connecté
        return redirect(url_for('login'))  # Redirige vers la page de connexion CAS

    df = pd.read_csv('scans_log.csv', names=['Place', 'IP Address', 'Scan Time', 'Website'])
    df['Scan Time'] = pd.to_datetime(df['Scan Time'])
    return df

# Analyser les données
def analyze_data(df):
    if not cas.username:  # Vérifie si l'utilisateur est connecté
        return redirect(url_for('login'))  # Redirige vers la page de connexion CAS
    
    scans_per_place = df['Place'].value_counts()
    scans_per_hour = df.set_index('Scan Time').resample('H').size()
    scans_per_ip = df['IP Address'].value_counts()
    return scans_per_place, scans_per_hour, scans_per_ip

# Créer des graphiques basiques avec Matplotlib
def plot_scans_per_place(scans_per_place):
    if not cas.username:  # Vérifie si l'utilisateur est connecté
        return redirect(url_for('login'))  # Redirige vers la page de connexion CAS

    plt.figure(figsize=(10, 6))
    scans_per_place.plot(kind='bar', color='skyblue')
    plt.title('Nombre de scans par lieu')
    plt.xlabel('Lieu')
    plt.ylabel('Nombre de scans')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig('static/scans_per_place.png')
    plt.close()

def plot_scans_per_hour(scans_per_hour):
    if not cas.username:  # Vérifie si l'utilisateur est connecté
        return redirect(url_for('login'))  # Redirige vers la page de connexion CAS

    plt.figure(figsize=(10, 6))
    scans_per_hour.plot(kind='line', color='orange')
    plt.title('Distribution des scans dans le temps (par heure)')
    plt.xlabel('Heure')
    plt.ylabel('Nombre de scans')
    plt.tight_layout()
    plt.savefig('static/scans_per_hour.png')
    plt.close()


# Route pour afficher les statistiques avec les nouveaux graphiques par jour et par heure
@app.route('/statistics')
def statistics():
    if not cas.username:  # Vérifie si l'utilisateur est connecté
        return redirect(url_for('login'))  # Redirige vers la page de connexion CAS

    df = load_log_data()

    # Scans par jour
    df['Scan Date'] = df['Scan Time'].dt.date
    scans_per_day = df.groupby('Scan Date').size().reset_index(name='Nombre de scans')

    # Scans par heure
    df['Scan Hour'] = df['Scan Time'].dt.hour
    scans_per_hour = df.groupby('Scan Hour').size().reset_index(name='Nombre de scans')

    # Création du graphique pour les scans par jour
    fig_day = px.bar(scans_per_day, x='Scan Date', y='Nombre de scans', title='Nombre de scans par jour')
    graph_day_html = pio.to_html(fig_day, full_html=False)

    # Création du graphique pour les scans par heure
    fig_hour = px.bar(scans_per_hour, x='Scan Hour', y='Nombre de scans', title='Distribution des scans par heure')
    graph_hour_html = pio.to_html(fig_hour, full_html=False)

    return render_template('statistics.html', graph_day_html=graph_day_html, graph_hour_html=graph_hour_html)


# Fonction pour enregistrer les données dans un fichier CSV
def log_scan(place, scan_time, web_site):
    if not cas.username:  # Vérifie si l'utilisateur est connecté
        return redirect(url_for('login'))  # Redirige vers la page de connexion CAS

    with open('scans_log.csv', mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([place, scan_time, web_site])

@app.route('/recap', methods=['GET', 'POST'])
def recap():
    if not cas.username:  # Vérifie si l'utilisateur est connecté
        return redirect(url_for('login'))  # Redirige vers la page de connexion CAS

    df = load_log_data()

    # Liste complète des sites web pour les filtres
    all_websites = df['Website'].unique()

    selected_website = None

    # Initialiser le tableau récapitulatif vide
    recap_table = pd.DataFrame()

    if request.method == 'POST':
        # Récupérer le site web sélectionné
        selected_website = request.form.get('website')

        # Filtrer le DataFrame en fonction du site web sélectionné
        if selected_website:
            df_filtered = df[df['Website'] == selected_website]

            # Compter le nombre de scans par lieu
            recap_table = df_filtered.groupby('Place').size().reset_index(name='Nombre de scans')

            # Ajouter une ligne de total avec pd.concat
            total_scans = recap_table['Nombre de scans'].sum()
            total_row = pd.DataFrame({'Place': ['Total'], 'Nombre de scans': [total_scans]})
            recap_table = pd.concat([recap_table, total_row], ignore_index=True)

    # Convertir le tableau récapitulatif en HTML
    recap_html = recap_table.to_html(classes='table table-striped table-bordered', index=False)

    return render_template('recap.html', all_websites=all_websites, recap_html=recap_html, selected_website=selected_website)


@app.route('/download_recap_csv', methods=['POST'])
def download_recap_csv():
    if not cas.username:  # Vérifie si l'utilisateur est connecté
        return redirect(url_for('login'))  # Redirige vers la page de connexion CAS

    df = load_log_data()

    # Filtrer selon le site web sélectionné
    selected_website = request.form.get('website')

    # Récupérer les données filtrées
    if selected_website:
        df_filtered = df[df['Website'] == selected_website]
        recap_table = df_filtered.groupby('Place').size().reset_index(name='Nombre de scans')

        # Ajouter la ligne de total
        total_scans = recap_table['Nombre de scans'].sum()
        total_row = pd.DataFrame({'Place': ['Total'], 'Nombre de scans': [total_scans]})
        recap_table = pd.concat([recap_table, total_row], ignore_index=True)

        # Générer le CSV
        response = make_response(recap_table.to_csv(index=False))
        response.headers["Content-Disposition"] = "attachment; filename=recap_table.csv"
        response.headers["Content-Type"] = "text/csv"

        return response


@app.route('/download_recap_excel', methods=['POST'])
def download_recap_excel():
    if not cas.username:  # Vérifie si l'utilisateur est connecté
        return redirect(url_for('login'))  # Redirige vers la page de connexion CAS

    df = load_log_data()

    # Filtrer selon le site web sélectionné
    selected_website = request.form.get('website')

    # Récupérer les données filtrées
    if selected_website:
        df_filtered = df[df['Website'] == selected_website]
        recap_table = df_filtered.groupby('Place').size().reset_index(name='Nombre de scans')

        # Ajouter la ligne de total
        total_scans = recap_table['Nombre de scans'].sum()
        total_row = pd.DataFrame({'Place': ['Total'], 'Nombre de scans': [total_scans]})
        recap_table = pd.concat([recap_table, total_row], ignore_index=True)

        # Créer le fichier Excel
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            recap_table.to_excel(writer, index=False)

        output.seek(0)
        response = make_response(output.getvalue())
        response.headers["Content-Disposition"] = "attachment; filename=recap_table.xlsx"
        response.headers["Content-Type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

        return response

@app.route('/dynamic_stats', methods=['GET', 'POST'])
def dynamic_stats():
    if not cas.username:  # Vérifie si l'utilisateur est connecté
        return redirect(url_for('login'))  # Redirige vers la page de connexion CAS

    df = load_log_data()

    # Liste complète des lieux et des sites web
    all_places = df['Place'].unique()
    all_websites = df['Website'].unique()

    # Initialiser les valeurs sélectionnées par défaut
    selected_places = []
    selected_websites = []
    start_date = None
    end_date = None

    if request.method == 'POST':
        # Récupérer les valeurs des filtres
        selected_places = request.form.getlist('places')
        selected_websites = request.form.getlist('websites')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')

        # Appliquer les filtres aux données
        if selected_places:
            df = df[df['Place'].isin(selected_places)]
        if selected_websites:
            df = df[df['Website'].isin(selected_websites)]
        if start_date and end_date:
            df = df[(df['Scan Time'] >= start_date) & (df['Scan Time'] <= end_date)]

    # Créer un graphique de courbe (line chart) avec Plotly
    fig = px.line(df, x='Scan Time', y='Place', color='Website', title='Scans filtrés par lieu et site web')
    graph_html = pio.to_html(fig, full_html=False)

    # Créer un tableau HTML à partir des données filtrées
    table_html = df.to_html(classes='table table-striped table-bordered', index=False)

    return render_template('dynamic_statistics.html', graph_html=graph_html,
                           table_html=table_html,
                           all_places=all_places, all_websites=all_websites,
                           selected_places=selected_places, selected_websites=selected_websites,
                           start_date=start_date, end_date=end_date)

# def generate_qr_code(data, fill_color, back_color, size):
#     if not cas.username:  # Vérifie si l'utilisateur est connecté
#         return redirect(url_for('login'))  # Redirige vers la page de connexion CAS

#     qr = qrcode.QRCode(
#         version=1,
#         error_correction=qrcode.constants.ERROR_CORRECT_L,
#         box_size=size // 40,
#         border=4,
#     )
#     qr.add_data(data)
#     qr.make(fit=True)
    
#     # Create the image with the given colors
#     img = qr.make_image(fill_color=fill_color, back_color=back_color)
#     img = img.resize((size, size))
    
#     return img
def generate_qr_code(data, fill_color, back_color, size, transparent_bg=False):
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=size // 40,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)

        if transparent_bg:
            # Configure le fond transparent
            back_color = (255, 255, 255, 0)  # Transparent
            img = qr.make_image(fill_color=fill_color, back_color=back_color).convert('RGBA')
            img = make_transparent(img)
        else:
            img = qr.make_image(fill_color=fill_color, back_color=back_color).convert('RGB')

        # Redimensionner l'image
        img = img.resize((size, size))
        return img
    except Exception as e:
        print(f"Error generating QR code: {e}")
        return None

# def generate_qr_code_with_logo(data, fill_color, back_color, size, logo_path, is_round=False):
#     if not cas.username:  # Vérifie si l'utilisateur est connecté
#         return redirect(url_for('login'))  # Redirige vers la page de connexion CAS

#     # Créer le QR code
#     qr = qrcode.QRCode(
#         version=1,
#         error_correction=qrcode.constants.ERROR_CORRECT_H,  # Correction d'erreur élevée pour supporter le logo
#         box_size=size // 40,
#         border=4,
#     )
#     qr.add_data(data)
#     qr.make(fit=True)
#     img = qr.make_image(fill_color=fill_color, back_color=back_color).convert('RGB')

#     # Redimensionner le QR code
#     img = img.resize((size, size))

#     # Ouvrir le logo
#     logo = Image.open(logo_path)

#     # Redimensionner le logo pour qu'il s'adapte au QR code (environ 20% de la taille du QR code)
#     logo_size = int(size * 0.2)
#     logo = logo.resize((logo_size, logo_size), Image.LANCZOS)

#     # Calculer la position centrale pour le logo
#     pos = ((img.size[0] - logo_size) // 2, (img.size[1] - logo_size) // 2)

#     # Ajouter le logo au centre du QR code
#     img.paste(logo, pos, logo if logo.mode == 'RGBA' else None)

#     # Si le format est rond, appliquer le masque circulaire
#     if is_round:
#         bigsize = (img.size[0] * 3, img.size[1] * 3)
#         mask = Image.new("L", bigsize, 0)
#         draw = ImageDraw.Draw(mask)
#         draw.ellipse((0, 0) + bigsize, fill=255)
#         mask = mask.resize(img.size, Image.LANCZOS)  # Utilise LANCZOS pour redimensionner le masque

#         # Appliquer le masque circulaire au QR code
#         img.putalpha(mask)

#         # Créer un fond blanc derrière le QR code rond
#         background = Image.new("RGBA", img.size, (255, 255, 255, 255))
#         background.paste(img, (0, 0), img)

#         return background

#     return img
def generate_qr_code_with_logo(data, fill_color, back_color, size, logo_path, is_round=False, transparent_bg=False):
    if not cas.username:
        return redirect(url_for('login'))

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=size // 40,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    if transparent_bg:
        back_color = None  # Set background to None for transparency

    img = qr.make_image(fill_color=fill_color, back_color=back_color).convert('RGBA')
    img = img.resize((size, size))

    if logo_path:
        logo = Image.open(logo_path)
        logo_size = int(size * 0.2)
        logo = logo.resize((logo_size, logo_size), Image.LANCZOS)
        pos = ((img.size[0] - logo_size) // 2, (img.size[1] - logo_size) // 2)
        img.paste(logo, pos, logo if logo.mode == 'RGBA' else None)

    if is_round:
        img = apply_round_mask(img)

    if transparent_bg:
        img = make_transparent(img)

    return img
def apply_round_mask(img):
    """
    Applique un masque circulaire à une image pour rendre les bords ronds.
    """
    # Créer une nouvelle image de la même taille que l'image originale, avec un canal alpha
    size = img.size
    mask = Image.new('L', size, 0)  # 'L' pour un masque en niveaux de gris

    # Dessiner un cercle blanc au centre du masque
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size[0], size[1]), fill=255)

    # Ajouter le masque à l'image originale
    img.putalpha(mask)

    return img
def generate_qr_code_round_only(data, fill_color, back_color, size):
    if not cas.username:  # Vérifie si l'utilisateur est connecté
        return redirect(url_for('login'))  # Redirige vers la page de connexion CAS

    # Créer le QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # Correction d'erreur élevée
        box_size=size // 40,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color=fill_color, back_color=back_color).convert('RGB')

    # Redimensionner le QR code
    img = img.resize((size, size))

    # Créer un masque circulaire
    bigsize = (img.size[0] * 3, img.size[1] * 3)
    mask = Image.new("L", bigsize, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0) + bigsize, fill=255)
    mask = mask.resize(img.size, Image.LANCZOS)  # Utilise LANCZOS pour redimensionner le masque

    # Appliquer le masque circulaire au QR code
    img.putalpha(mask)

    # Créer un fond blanc derrière le QR code rond
    background = Image.new("RGBA", img.size, (255, 255, 255, 255))
    background.paste(img, (0, 0), img)

    return background

def make_transparent(img):
    datas = img.getdata()
    new_data = []
    for item in datas:
        # Si le pixel est blanc (255, 255, 255), on le rend transparent
        if item[:3] == (255, 255, 255):  # Blanc
            new_data.append((255, 255, 255, 0))  # Transparent
        else:
            new_data.append(item)
    img.putdata(new_data)
    return img

# @app.route('/', methods=['GET', 'POST'])
# def index():
#     if not cas.username:  # Vérifie si l'utilisateur est connecté
#         return redirect(url_for('login'))  # Redirige vers la page de connexion CAS

#     if request.method == 'POST':
#         redirect_url = request.form['base_url']
#         places = request.form['places'].splitlines()

#         use_default_colors = 'use_default_colors' in request.form
#         if use_default_colors:
#             fill_color = "#30B4CD"
#             back_color = "#FEB30E"
#         else:
#             fill_color = request.form['fill_color']
#             back_color = request.form['back_color']

#         size = int(request.form['size'])
#         qr_format = request.form['qr_format']  # Récupérer le format choisi (carré/rond)

#         # Vérifiez si un logo a été téléchargé
#         logo = request.files['logo']
#         logo_path = None

#         # Si un logo a été téléchargé, enregistrez-le temporairement
#         if logo and logo.filename != '':
#             logo_path = os.path.join('static', logo.filename)
#             logo.save(logo_path)

#         qr_codes = []
#         pdf_files = []  # List to store the generated PDF filenames

#         for place in places:
#             full_url = f"{request.host_url}tracker?place={place.strip()}&redirect={redirect_url}"

#             # Cas pour carré ou rond
#             if qr_format == 'round':  # Si le format est rond
#                 if logo_path:  # QR code rond avec logo
#                     img = generate_qr_code_with_logo(full_url, fill_color, back_color, size, logo_path, is_round=True)
#                 else:  # QR code rond sans logo
#                     img = generate_qr_code_round_only(full_url, fill_color, back_color, size)
#             else:  # Carré par défaut (avec ou sans logo)
#                 if logo_path:  # Carré avec logo
#                     img = generate_qr_code_with_logo(full_url, fill_color, back_color, size, logo_path)
#                 else:  # Carré sans logo
#                     img = generate_qr_code(full_url, fill_color, back_color, size)

#             img_io = BytesIO()
#             img.save(img_io, 'PNG')
#             img_io.seek(0)

#             img_base64 = base64.b64encode(img_io.getvalue()).decode('utf-8')
#             qr_codes.append((place, img_base64))

#             # Generate PDF for this QR code
#             pdf_filename = create_pdf(place, img_base64, redirect_url)
#             pdf_files.append(pdf_filename)  # Add the filename to the list

#         # Zip the QR codes and PDF files together and pass it to the template
#         qr_code_pdf_pairs = zip(qr_codes, pdf_files)

#         # Si un logo a été utilisé, vous pouvez le supprimer après l'utilisation
#         if logo_path:
#             os.remove(logo_path)

#         return render_template('qr_codes.html', qr_code_pdf_pairs=qr_code_pdf_pairs)

#     return render_template('index.html')
@app.route('/', methods=['GET', 'POST'])
def index():
    if not cas.username:  # Vérifie si l'utilisateur est connecté
        return redirect(url_for('login'))  # Redirige vers la page de connexion CAS

    if request.method == 'POST':
        # Ajoutez ces lignes pour déboguer
        print("Form data received:", request.form)
        print("Files uploaded:", request.files)

        redirect_url = request.form['base_url']
        places = request.form['places'].splitlines()

        use_default_colors = 'use_default_colors' in request.form
        transparent_bg = 'transparent_bg' in request.form
        if use_default_colors:
            fill_color = "#30B4CD"
            back_color = "#FEB30E"
        else:
            fill_color = request.form['fill_color']
            back_color = request.form['back_color']

        size = int(request.form['size'])
        qr_format = request.form['qr_format']

        logo = request.files['logo']
        logo_path = None
        if logo and logo.filename != '':
            logo_path = os.path.join('static', logo.filename)
            logo.save(logo_path)

        qr_codes = []
        pdf_files = []

        for place in places:
            full_url = f"{request.host_url}tracker?place={place.strip()}&redirect={redirect_url}"

            if qr_format == 'round':
                if logo_path:
                    img = generate_qr_code_with_logo(full_url, fill_color, back_color, size, logo_path, is_round=True, transparent_bg=transparent_bg)
                else:
                    img = generate_qr_code_round_only(full_url, fill_color, back_color, size)
            else:
                if logo_path:
                    img = generate_qr_code_with_logo(full_url, fill_color, back_color, size, logo_path, transparent_bg=transparent_bg)
                else:
                    img = generate_qr_code(full_url, fill_color, back_color, size, transparent_bg=transparent_bg)

            img_io = BytesIO()
            img.save(img_io, 'PNG')
            img_io.seek(0)

            img_base64 = base64.b64encode(img_io.getvalue()).decode('utf-8')
            qr_codes.append((place, img_base64))

            pdf_filename = create_pdf(place, img_base64, redirect_url)
            pdf_files.append(pdf_filename)

        if logo_path:
            os.remove(logo_path)

        print("Generated QR codes:", qr_codes)
        print("Generated PDFs:", pdf_files)

        if not qr_codes:
            print("No QR codes generated. Check input data.")
            
        qr_code_pdf_pairs = list(zip(qr_codes, pdf_files))  # Convertir en liste
        return render_template('qr_codes.html', qr_code_pdf_pairs=qr_code_pdf_pairs)


    return render_template('index.html')


@app.route('/download_png/<place>', methods=['GET'])
def download_png(place):
    try:
        # Générer le QR code
        qr_code_data = f"{request.host_url}tracker?place={place.strip()}"
        fill_color = "#30B4CD"  # Bleu
        back_color = None  # Fond transparent
        size = 400  # Taille du QR code

        img = generate_qr_code(qr_code_data, fill_color, back_color, size, transparent_bg=True)

        # Sauvegarder l'image en mémoire
        img_io = BytesIO()
        img.save(img_io, 'PNG')  # Format PNG
        img_io.seek(0)

        # Retourner l'image téléchargée
        return send_file(img_io, mimetype='image/png', as_attachment=True, download_name=f"{place}.png")
    except Exception as e:
        print(f"Error generating PNG for {place}: {e}")
        return "Erreur lors du téléchargement du PNG", 500


# Route pour capturer les scans des QR codes
@app.route('/tracker', methods=['GET'])
def tracker():
    place = request.args.get('place')
    scan_time = datetime.now()
    redirect_url = request.args.get('redirect')
    log_scan(place, scan_time, redirect_url)
    return redirect("http://www." + redirect_url, code=302)

# Fonction pour créer un PDF
def create_pdf(place, img_data, base_url):
    
    if not cas.username:  # Vérifie si l'utilisateur est connecté
        return redirect(url_for('login'))  # Redirige vers la page de connexion CAS

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"QR Code pour le lieu: {place}", ln=True, align="C")
    img_path = f"temp_{place}.png"
    with open(img_path, "wb") as img_file:
        img_file.write(base64.b64decode(img_data))
    pdf.image(img_path, x=(210-100)/2, y=30, w=100, h=100)
    pdf.ln(100)
    pdf.cell(200, 10, txt=f"Lien associé: {base_url}", ln=True, align="C")
    pdf_filename = f"qr_code_{place}.pdf"
    pdf.output(pdf_filename)
    os.remove(img_path)
    return pdf_filename

# Route pour télécharger un PDF
@app.route('/download/<filename>')
def download_pdf(filename):
    if not cas.username:  # Vérifie si l'utilisateur est connecté
        return redirect(url_for('login'))  # Redirige vers la page de connexion CAS

    return send_file(filename, as_attachment=True)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
