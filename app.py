from flask import Flask, render_template, request, redirect, send_file,  make_response
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

app = Flask(__name__)


@app.route('/download_filtered_csv', methods=['POST'])
def download_filtered_csv():
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
    df = pd.read_csv('scans_log.csv', names=['Place', 'IP Address', 'Scan Time', 'Website'])
    df['Scan Time'] = pd.to_datetime(df['Scan Time'])
    return df

# Analyser les données
def analyze_data(df):
    scans_per_place = df['Place'].value_counts()
    scans_per_hour = df.set_index('Scan Time').resample('H').size()
    scans_per_ip = df['IP Address'].value_counts()
    return scans_per_place, scans_per_hour, scans_per_ip

# Créer des graphiques basiques avec Matplotlib
def plot_scans_per_place(scans_per_place):
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
    with open('scans_log.csv', mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([place, scan_time, web_site])

@app.route('/recap', methods=['GET', 'POST'])
def recap():
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

# Fonction pour générer un QR code avec des couleurs personnalisées
# def generate_qr_code(data, fill_color, back_color, size):
#     qr = qrcode.QRCode(
#         version=1,
#         error_correction=qrcode.constants.ERROR_CORRECT_L,
#         box_size=size // 40,
#         border=4,
#     )
#     qr.add_data(data)
#     qr.make(fit=True)
#     img = qr.make_image(fill_color=fill_color, back_color=back_color).resize((size, size))
#     return img

def generate_qr_code(data, fill_color, back_color, size):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=size // 40,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    
    # Create the image with the given colors
    img = qr.make_image(fill_color=fill_color, back_color=back_color)
    img = img.resize((size, size))
    
    return img

def generate_qr_code_with_logo(data, fill_color, back_color, size, logo_path, is_round=False):
    # Créer le QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # Correction d'erreur élevée pour supporter le logo
        box_size=size // 40,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color=fill_color, back_color=back_color).convert('RGB')

    # Redimensionner le QR code
    img = img.resize((size, size))

    # Ouvrir le logo
    logo = Image.open(logo_path)

    # Redimensionner le logo pour qu'il s'adapte au QR code (environ 20% de la taille du QR code)
    logo_size = int(size * 0.2)
    logo = logo.resize((logo_size, logo_size), Image.LANCZOS)

    # Calculer la position centrale pour le logo
    pos = ((img.size[0] - logo_size) // 2, (img.size[1] - logo_size) // 2)

    # Ajouter le logo au centre du QR code
    img.paste(logo, pos, logo if logo.mode == 'RGBA' else None)

    # Si le format est rond, appliquer le masque circulaire
    if is_round:
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

    return img

# def generate_qr_code_with_logo(data, fill_color, back_color, size, logo_path):
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

#     # Ouvrir le logo
#     logo = Image.open(logo_path)

#     # Redimensionner le logo pour qu'il s'adapte au QR code
#     logo_size = int(size * 0.2)
#     logo = logo.resize((logo_size, logo_size))

#     # Calculer la position centrale pour le logo
#     pos = ((img.size[0] - logo_size) // 2, (img.size[1] - logo_size) // 2)

#     # Ajouter le logo au centre du QR code
#     img.paste(logo, pos)

#     return img

def generate_qr_code_round_only(data, fill_color, back_color, size):
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

@app.route('/', methods=['GET', 'POST'])
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        redirect_url = request.form['base_url']
        places = request.form['places'].splitlines()

        use_default_colors = 'use_default_colors' in request.form
        if use_default_colors:
            fill_color = "#30B4CD"
            back_color = "#FEB30E"
        else:
            fill_color = request.form['fill_color']
            back_color = request.form['back_color']

        size = int(request.form['size'])
        qr_format = request.form['qr_format']  # Récupérer le format choisi (carré/rond)

        # Vérifiez si un logo a été téléchargé
        logo = request.files['logo']
        logo_path = None

        # Si un logo a été téléchargé, enregistrez-le temporairement
        if logo and logo.filename != '':
            logo_path = os.path.join('static', logo.filename)
            logo.save(logo_path)

        qr_codes = []
        pdf_files = []  # List to store the generated PDF filenames

        for place in places:
            full_url = f"{request.host_url}tracker?place={place.strip()}&redirect={redirect_url}"

            # Cas pour carré ou rond
            if qr_format == 'round':  # Si le format est rond
                if logo_path:  # QR code rond avec logo
                    img = generate_qr_code_with_logo(full_url, fill_color, back_color, size, logo_path, is_round=True)
                else:  # QR code rond sans logo
                    img = generate_qr_code_round_only(full_url, fill_color, back_color, size)
            else:  # Carré par défaut (avec ou sans logo)
                if logo_path:  # Carré avec logo
                    img = generate_qr_code_with_logo(full_url, fill_color, back_color, size, logo_path)
                else:  # Carré sans logo
                    img = generate_qr_code(full_url, fill_color, back_color, size)

            img_io = BytesIO()
            img.save(img_io, 'PNG')
            img_io.seek(0)

            img_base64 = base64.b64encode(img_io.getvalue()).decode('utf-8')
            qr_codes.append((place, img_base64))

            # Generate PDF for this QR code
            pdf_filename = create_pdf(place, img_base64, redirect_url)
            pdf_files.append(pdf_filename)  # Add the filename to the list

        # Zip the QR codes and PDF files together and pass it to the template
        qr_code_pdf_pairs = zip(qr_codes, pdf_files)

        # Si un logo a été utilisé, vous pouvez le supprimer après l'utilisation
        if logo_path:
            os.remove(logo_path)

        return render_template('qr_codes.html', qr_code_pdf_pairs=qr_code_pdf_pairs)

    return render_template('index.html')

# def index():
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

#         # Si un logo a été utilisé, vous pouvez le supprimer après l'utilisation
#         if logo_path:
#             os.remove(logo_path)

#         return render_template('qr_codes.html', qr_codes=qr_codes)

#     return render_template('index.html')

# Route pour capturer les scans des QR codes
@app.route('/tracker', methods=['GET'])
def tracker():
    place = request.args.get('place')
    scan_time = datetime.datetime.now()
    redirect_url = request.args.get('redirect')
    log_scan(place, scan_time, redirect_url)
    return redirect("http://www." + redirect_url, code=302)

# Fonction pour créer un PDF
def create_pdf(place, img_data, base_url):
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
    return send_file(filename, as_attachment=True)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

# from flask import Flask, render_template, request, redirect, send_file
# import qrcode
# from io import BytesIO
# import base64
# import datetime
# import csv
# from fpdf import FPDF
# import os
# import pandas as pd
# import matplotlib.pyplot as plt
# import plotly.express as px
# import plotly.io as pio

# app = Flask(__name__)

# # Charger les logs du fichier CSV
# def load_log_data():
#     df = pd.read_csv('scans_log.csv', names=['Place', 'IP Address', 'Scan Time', 'Website'])
#     df['Scan Time'] = pd.to_datetime(df['Scan Time'])
#     return df

# # Analyser les données
# def analyze_data(df):
#     scans_per_place = df['Place'].value_counts()
#     scans_per_hour = df.set_index('Scan Time').resample('H').size()
#     scans_per_ip = df['IP Address'].value_counts()
#     return scans_per_place, scans_per_hour, scans_per_ip

# # Créer des graphiques basiques avec Matplotlib
# def plot_scans_per_place(scans_per_place):
#     plt.figure(figsize=(10, 6))
#     scans_per_place.plot(kind='bar', color='skyblue')
#     plt.title('Nombre de scans par lieu')
#     plt.xlabel('Lieu')
#     plt.ylabel('Nombre de scans')
#     plt.xticks(rotation=45)
#     plt.tight_layout()
#     plt.savefig('static/scans_per_place.png')
#     plt.close()

# def plot_scans_per_hour(scans_per_hour):
#     plt.figure(figsize=(10, 6))
#     scans_per_hour.plot(kind='line', color='orange')
#     plt.title('Distribution des scans dans le temps (par heure)')
#     plt.xlabel('Heure')
#     plt.ylabel('Nombre de scans')
#     plt.tight_layout()
#     plt.savefig('static/scans_per_hour.png')
#     plt.close()

# # Route pour afficher les statistiques avec les graphiques statiques
# @app.route('/statistics')
# def statistics():
#     df = load_log_data()
#     scans_per_place, scans_per_hour, scans_per_ip = analyze_data(df)
#     plot_scans_per_place(scans_per_place)
#     plot_scans_per_hour(scans_per_hour)
#     return render_template('statistics.html')


# # @app.route('/dynamic_line_chart', methods=['GET', 'POST'])
# # def dynamic_line_chart():
# #     df = load_log_data()

# #     # Liste complète des lieux et des sites web
# #     all_places = df['Place'].unique()
# #     all_websites = df['Website'].unique()

# #     # Initialiser les valeurs sélectionnées par défaut
# #     selected_places = []
# #     selected_websites = []
# #     start_date = None
# #     end_date = None

# #     if request.method == 'POST':
# #         # Récupérer les valeurs des filtres
# #         selected_places = request.form.getlist('places')
# #         selected_websites = request.form.getlist('websites')
# #         start_date = request.form.get('start_date')
# #         end_date = request.form.get('end_date')

# #         # Appliquer les filtres aux données
# #         if selected_places:
# #             df = df[df['Place'].isin(selected_places)]
# #         if selected_websites:
# #             df = df[df['Website'].isin(selected_websites)]
# #         if start_date and end_date:
# #             df = df[(df['Scan Time'] >= start_date) & (df['Scan Time'] <= end_date)]

# #     # Créer un graphique de courbe en fonction du temps (ou d'une autre métrique)
# #     fig = px.line(df, x='Scan Time', y='Place', color='Website', title='Scans filtrés par lieu et site web')

# #     # Générer le HTML du graphique Plotly
# #     graph_html = pio.to_html(fig, full_html=False)

# #     return render_template('dynamic_statistics.html', graph_html=graph_html,
# #                            all_places=all_places, all_websites=all_websites,
# #                            selected_places=selected_places, selected_websites=selected_websites,
# #                            start_date=start_date, end_date=end_date)

# # Fonction pour enregistrer les données dans un fichier CSV
# def log_scan(place, ip_address, scan_time, web_site):
#     with open('scans_log.csv', mode='a', newline='') as file:
#         writer = csv.writer(file)
#         writer.writerow([place, ip_address, scan_time, web_site])

# @app.route('/dynamic_stats', methods=['GET', 'POST'])
# def dynamic_stats():
#     df = load_log_data()

#     # Liste complète des lieux et des sites web
#     all_places = df['Place'].unique()
#     all_websites = df['Website'].unique()

#     # Initialiser les valeurs sélectionnées par défaut
#     selected_places = []
#     selected_websites = []
#     start_date = None
#     end_date = None

#     if request.method == 'POST':
#         # Récupérer les valeurs des filtres
#         selected_places = request.form.getlist('places')
#         selected_websites = request.form.getlist('websites')
#         start_date = request.form.get('start_date')
#         end_date = request.form.get('end_date')

#         # Appliquer les filtres aux données
#         if selected_places:
#             df = df[df['Place'].isin(selected_places)]
#         if selected_websites:
#             df = df[df['Website'].isin(selected_websites)]
#         if start_date and end_date:
#             df = df[(df['Scan Time'] >= start_date) & (df['Scan Time'] <= end_date)]

#     # Créer un graphique de courbe (line chart) avec Plotly
#     fig = px.line(df, x='Scan Time', y='Place', color='Website', title='Scans filtrés par lieu et site web')
#     graph_html = pio.to_html(fig, full_html=False)

#     # Créer un tableau HTML à partir des données filtrées
#     table_html = df.to_html(classes='table table-striped table-bordered', index=False)

#     return render_template('dynamic_statistics.html', graph_html=graph_html,
#                            table_html=table_html,
#                            all_places=all_places, all_websites=all_websites,
#                            selected_places=selected_places, selected_websites=selected_websites,
#                            start_date=start_date, end_date=end_date)

# # Fonction pour générer un QR code avec des couleurs personnalisées
# def generate_qr_code(data, fill_color, back_color, size):
#     qr = qrcode.QRCode(
#         version=1,
#         error_correction=qrcode.constants.ERROR_CORRECT_L,
#         box_size=size // 40,
#         border=4,
#     )
#     qr.add_data(data)
#     qr.make(fit=True)
#     img = qr.make_image(fill_color=fill_color, back_color=back_color).resize((size, size))
#     return img

# # Générer les graphiques statiques
# @app.route('/', methods=['GET', 'POST'])
# def index():
#     try:
#         if request.method == 'POST':
#             redirect_url = request.form['base_url']
#             places = request.form['places'].splitlines()

#             use_default_colors = 'use_default_colors' in request.form
#             if use_default_colors:
#                 fill_color = "#30B4CD"
#                 back_color = "#FEB30E"
#             else:
#                 fill_color = request.form['fill_color']
#                 back_color = request.form['back_color']

#             size = int(request.form['size'])

#             qr_codes = []
#             for place in places:
#                 # full_url = f"http://127.0.0.1:5000/tracker?place={place.strip()}&redirect={redirect_url}"
#                 full_url = f"{request.host_url}tracker?place={place.strip()}&redirect={redirect_url}"

#                 img = generate_qr_code(full_url, fill_color, back_color, size)

#                 img_io = BytesIO()
#                 img.save(img_io, 'PNG')
#                 img_io.seek(0)

#                 img_base64 = base64.b64encode(img_io.getvalue()).decode('utf-8')
#                 qr_codes.append((place, img_base64))

#             return render_template('qr_codes.html', qr_codes=qr_codes)

#         return render_template('index.html')
#     except Exception as e:
#         # Afficher l'erreur dans les logs
#         print(f"Une erreur est survenue : {str(e)}")
#         return f"Une erreur est survenue : {str(e)}", 500

# # Page des graphiques dynamiques (HTML)
# @app.route('/tracker', methods=['GET'])
# def tracker():
#     place = request.args.get('place')
#     ip_address = request.remote_addr
#     scan_time = datetime.datetime.now()
#     redirect_url = request.args.get('redirect')
#     log_scan(place, ip_address, scan_time, redirect_url)
#     return redirect("http://" + redirect_url, code=302)

# # Fonction pour créer un PDF
# def create_pdf(place, img_data, base_url):
#     pdf = FPDF()
#     pdf.add_page()
#     pdf.set_font("Arial", size=12)
#     pdf.cell(200, 10, txt=f"QR Code pour le lieu: {place}", ln=True, align="C")
#     img_path = f"temp_{place}.png"
#     with open(img_path, "wb") as img_file:
#         img_file.write(base64.b64decode(img_data))
#     pdf.image(img_path, x=(210-100)/2, y=30, w=100, h=100)
#     pdf.ln(100)
#     pdf.cell(200, 10, txt=f"Lien associé: {base_url}", ln=True, align="C")
#     pdf_filename = f"qr_code_{place}.pdf"
#     pdf.output(pdf_filename)
#     os.remove(img_path)
#     return pdf_filename

# # Route pour télécharger un PDF
# @app.route('/download/<filename>')
# def download_pdf(filename):
#     return send_file(filename, as_attachment=True)


# if __name__ == '__main__':
#     port = int(os.environ.get('PORT', 5000))  # Utilise le port fourni par la plateforme ou 5000 par défaut
#     app.run(host='0.0.0.0', port=port, debug=True)

# from flask import Flask, render_template, request, redirect, send_file
# import qrcode
# from io import BytesIO
# import base64
# import datetime
# import csv
# from fpdf import FPDF
# import os
# import pandas as pd
# import matplotlib.pyplot as plt

# app = Flask(__name__)


# def load_log_data():
#     # Charger les données du fichier CSV dans un DataFrame
#     df = pd.read_csv('scans_log.csv', names=['Place', 'IP Address', 'Scan Time', 'Website'])

#     # Convertir la colonne "Scan Time" en format datetime
#     df['Scan Time'] = pd.to_datetime(df['Scan Time'])

#     return df


# def analyze_data(df):
#     # Nombre total de scans par lieu
#     scans_per_place = df['Place'].value_counts()

#     # Distribution des scans dans le temps (par heure)
#     scans_per_hour = df.set_index('Scan Time').resample('H').size()

#     # Nombre de scans par adresse IP
#     scans_per_ip = df['IP Address'].value_counts()

#     return scans_per_place, scans_per_hour, scans_per_ip

# def plot_scans_per_place(scans_per_place):
#     plt.figure(figsize=(10, 6))
#     scans_per_place.plot(kind='bar', color='skyblue')
#     plt.title('Nombre de scans par lieu')
#     plt.xlabel('Lieu')
#     plt.ylabel('Nombre de scans')
#     plt.xticks(rotation=45)
#     plt.tight_layout()
#     plt.savefig('static/scans_per_place.png')  # Sauvegarder le graphique
#     plt.show()

# def plot_scans_per_hour(scans_per_hour):
#     plt.figure(figsize=(10, 6))
#     scans_per_hour.plot(kind='line', color='orange')
#     plt.title('Distribution des scans dans le temps (par heure)')
#     plt.xlabel('Heure')
#     plt.ylabel('Nombre de scans')
#     plt.tight_layout()
#     plt.savefig('static/scans_per_hour.png')  # Sauvegarder le graphique
#     plt.show()


# @app.route('/statistics')
# def statistics():
#     # Charger les données du fichier CSV
#     df = load_log_data()

#     # Analyser les données
#     scans_per_place, scans_per_hour, scans_per_ip = analyze_data(df)

#     # Générer les graphiques
#     plot_scans_per_place(scans_per_place)
#     plot_scans_per_hour(scans_per_hour)

#     # Afficher la page des statistiques avec les graphiques
#     return render_template('statistics.html')

# # Fonction pour générer un QR code avec des couleurs personnalisées
# def generate_qr_code(data, fill_color, back_color, size):
#     qr = qrcode.QRCode(
#         version=1,
#         error_correction=qrcode.constants.ERROR_CORRECT_L,
#         box_size=size // 40,  # Ajuster le 'box_size' selon la taille choisie
#         border=4,
#     )
#     qr.add_data(data)
#     qr.make(fit=True)

#     # Créer une image QR code avec des couleurs et une taille personnalisées
#     img = qr.make_image(fill_color=fill_color, back_color=back_color).resize((size, size))
#     return img


# # Fonction pour enregistrer les données dans un fichier CSV
# def log_scan(place, ip_address, scan_time, web_site):
#     with open('scans_log.csv', mode='a', newline='') as file:
#         writer = csv.writer(file)
#         writer.writerow([place, ip_address, scan_time, web_site])

# # Page d'accueil avec le formulaire pour générer les QR codes
# @app.route('/', methods=['GET', 'POST'])
# def index():
#     if request.method == 'POST':
#         # Récupérer l'URL de redirection et les lieux depuis le formulaire
#         redirect_url = request.form['base_url']
#         places = request.form['places'].splitlines()
#  # Vérifier si l'utilisateur souhaite utiliser les couleurs par défaut
#         use_default_colors = 'use_default_colors' in request.form

#         if use_default_colors:
#             # Couleurs par défaut de l'Université d'Évry
#             fill_color = "#30B4CD"  # couleur
#             back_color = "#FEB30E"  # couleur background
#         else:
#             # Couleurs personnalisées
#             fill_color = request.form['fill_color']
#             back_color = request.form['back_color']

#         size = int(request.form['size'])  # Récupérer la taille sélectionnée

#         # Liste pour stocker les QR codes générés
#         qr_codes = []

#         for place in places:
#             # Créer l'URL unique pour chaque lieu et y inclure l'URL de redirection
#             full_url = f"http://127.0.0.1:5000/tracker?place={place.strip()}&redirect={redirect_url}"

#             # Générer le QR code avec les couleurs personnalisées
#             img = generate_qr_code(full_url, fill_color, back_color, size)

#             # Sauvegarder l'image dans un objet BytesIO (en mémoire)
#             img_io = BytesIO()
#             img.save(img_io, 'PNG')
#             img_io.seek(0)

#             # Encoder l'image en base64
#             img_base64 = base64.b64encode(img_io.getvalue()).decode('utf-8')

#             # Générer un PDF pour chaque QR code
#             pdf_filename = create_pdf(place.strip(), img_base64, full_url)

#             # Ajouter le lieu, l'image en base64, et le fichier PDF à la liste
#             qr_codes.append((place, img_base64, pdf_filename))  # Trois valeurs maintenant


#         # Afficher la page avec les QR codes et les fichiers PDF
#         return render_template('qr_codes.html', qr_codes=qr_codes)

#     # Page d'accueil avec le formulaire
#     return render_template('index.html')

# # Route pour capturer les scans des QR codes
# @app.route('/tracker', methods=['GET'])
# def tracker():
#     # Récupère le paramètre 'place' de l'URL
#     place = request.args.get('place')

#     # Récupère l'adresse IP du scanner
#     ip_address = request.remote_addr

#     # Enregistre l'heure du scan
#     scan_time = datetime.datetime.now()

#     # Récupérer l'URL de redirection à partir du paramètre 'redirect'
#     redirect_url = request.args.get('redirect')

#     # Enregistre les informations dans un fichier CSV
#     log_scan(place, ip_address, scan_time, redirect_url)

#     # Rediriger l'utilisateur vers l'URL spécifiée
#     return redirect("http://" + redirect_url, code=302)

# def create_pdf(place, img_data, base_url):
#     pdf = FPDF()
#     pdf.add_page()

#     # Définir la police pour le titre
#     pdf.set_font("Arial", size=12)

#     # Centrer le texte du titre (largeur de la page = 210mm, donc centrer sur 200mm)
#     pdf.cell(200, 10, txt=f"QR Code pour le lieu: {place}", ln=True, align="C")

#     # Sauvegarder l'image temporairement pour l'insérer dans le PDF
#     img_path = f"temp_{place}.png"
#     with open(img_path, "wb") as img_file:
#         img_file.write(base64.b64decode(img_data))

#     pdf.ln(100)

#     # Ajouter l'image du QR code au PDF et la centrer
#     # On peut ajuster les positions 'x' et 'y' pour centrer l'image (largeur de la page = 210mm)
#     pdf.image(img_path, x=(210-100)/2, y=30, w=100, h=100)

#     # Sauter quelques lignes avant d'ajouter le lien
#     pdf.ln(100)


#     # Ajouter le lien en dessous du QR code et le centrer
#     pdf.cell(200, 10, txt=f"Lien associé: {base_url}", ln=True, align="C")

#     # Nom du fichier PDF basé sur le lieu
#     pdf_filename = f"qr_code_{place}.pdf"
#     pdf.output(pdf_filename)

#     # Supprimer l'image temporaire
#     os.remove(img_path)

#     return pdf_filename

# # Route pour télécharger un PDF
# @app.route('/download/<filename>')
# def download_pdf(filename):
#     return send_file(filename, as_attachment=True)

# if __name__ == '__main__':
#     app.run(debug=True)

# from flask import Flask, render_template, request, redirect, send_file
# import qrcode
# from io import BytesIO
# import base64
# import datetime
# import csv
# from fpdf import FPDF
# import os

# app = Flask(__name__)

# # Fonction pour générer un QR code avec des couleurs personnalisées
# def generate_qr_code(data, fill_color, back_color):
#     qr = qrcode.QRCode(
#         version=1,
#         error_correction=qrcode.constants.ERROR_CORRECT_L,
#         box_size=10,
#         border=4,
#     )
#     qr.add_data(data)
#     qr.make(fit=True)

#     # Créer une image QR code avec des couleurs personnalisées
#     img = qr.make_image(fill_color=fill_color, back_color=back_color)
#     return img
# # Fonction pour enregistrer les données dans un fichier CSV
# def log_scan(place, ip_address, scan_time, web_site):
#     with open('scans_log.csv', mode='a', newline='') as file:
#         writer = csv.writer(file)
#         writer.writerow([place, ip_address, scan_time, web_site])

# # Page d'accueil avec le formulaire pour générer les QR codes
# @app.route('/', methods=['GET', 'POST'])
# def index():
#     if request.method == 'POST':
#         # Récupérer l'URL de redirection et les lieux depuis le formulaire
#         redirect_url = request.form['base_url']
#         places = request.form['places'].splitlines()

#         fill_color = request.form['fill_color']  # Couleur des motifs
#         back_color = request.form['back_color']  # Couleur de fond
#         # Liste pour stocker les QR codes générés
#         qr_codes = []
#         pdf_files = []  # Liste pour stocker les fichiers PDF générés

#         for place in places:
#             # Créer l'URL unique pour chaque lieu et y inclure l'URL de redirection
#             full_url = f"http://127.0.0.1:5000/tracker?place={place.strip()}&redirect={redirect_url}"

#             # Générer le QR code
#             #img = qrcode.make(full_url)

#             img = generate_qr_code(full_url, fill_color, back_color)
#             # Sauvegarder l'image dans un objet BytesIO (en mémoire)²
#             img_io = BytesIO()
#             img.save(img_io, 'PNG')
#             img_io.seek(0)

#             # Encoder l'image en base64
#             img_base64 = base64.b64encode(img_io.getvalue()).decode('utf-8')

#             # Ajouter les données du QR code à la liste (place et image en base64)
#             qr_codes.append((place, img_base64))

#             # Générer un PDF pour chaque QR code
#             pdf_filename = create_pdf(place.strip(), img_base64, full_url)
#             pdf_files.append(pdf_filename)
#         # Afficher la page avec les QR codes
#         return render_template('qr_codes.html', qr_codes=qr_codes)

#     # Page d'accueil avec le formulaire
#     return render_template('index.html')

# # Route pour capturer les scans des QR codes
# @app.route('/tracker', methods=['GET'])
# def tracker():
#     # Récupère le paramètre 'place' de l'URL
#     place = request.args.get('place')

#     # Récupère l'adresse IP du scanner
#     ip_address = request.remote_addr

#     # Enregistre l'heure du scan
#     scan_time = datetime.datetime.now()

#     # Récupérer l'URL de redirection à partir du paramètre 'redirect'
#     redirect_url = request.args.get('redirect')
#     # Enregistre les informations dans un fichier CSV ou base de données
#     log_scan(place, ip_address, scan_time, redirect_url)


#     # Rediriger l'utilisateur vers l'URL spécifiée
#     return redirect("http://" +redirect_url, code=302)

# # Fonction pour créer un PDF avec le QR code
# def create_pdf(place, img_data, base_url):
#     pdf = FPDF()
#     pdf.add_page()

#     # Ajouter le titre
#     pdf.set_font("Arial", size=12)
#     pdf.cell(200, 10, txt=f"QR Code pour le lieu: {place}", ln=True, align="C")

#     # Sauvegarder l'image temporairement pour l'insérer dans le PDF
#     img_path = f"temp_{place}.png"
#     with open(img_path, "wb") as img_file:
#         img_file.write(base64.b64decode(img_data))

#     # Ajouter l'image du QR code au PDF
#     pdf.image(img_path, x=10, y=20, w=100, h=100)

#     # Ajouter le lien en dessous du QR code
#     pdf.ln(110)
#     pdf.cell(200, 10, txt=f"Lien associé: {base_url}", ln=True, align="C")

#     # Nom du fichier PDF basé sur le lien et la place
#     pdf_filename = f"qr_code_{place}.pdf"
#     pdf.output(pdf_filename)

#     # Supprimer l'image temporaire
#     os.remove(img_path)

#     return pdf_filename
# # Route pour télécharger un PDF
# @app.route('/download/<filename>')
# def download_pdf(filename):
#     return send_file(filename, as_attachment=True)

# if __name__ == '__main__':
#     app.run(debug=True)


# from flask import Flask, request, redirect
# import datetime
# import csv

# app = Flask(__name__)

# # Fonction pour enregistrer les données dans un fichier CSV
# def log_scan(place, ip_address, scan_time):
#     with open('scans_log.csv', mode='a', newline='') as file:
#         writer = csv.writer(file)
#         writer.writerow([place, ip_address, scan_time])

# # Route pour capturer les scans des QR codes
# @app.route('/tracker', methods=['GET'])
# def tracker():
#     # Récupère le paramètre 'place' de l'URL
#     place = request.args.get('place')

#     # Récupère l'adresse IP du scanner
#     ip_address = request.remote_addr

#     # Enregistre l'heure du scan
#     scan_time = datetime.datetime.now()

#     # Enregistre les informations dans un fichier ou une base de données
#     log_scan(place, ip_address, scan_time)

#     # Redirige l'utilisateur vers Google après avoir enregistré les informations
#     return redirect("https://www.google.com", code=302)
#     #return redirect("https://www.univ-evry.fr/accueil.html", code=302)

# if __name__ == '__main__':
#     app.run(debug=True)

#*********************************************************************************************************************
# from flask import Flask, request, redirect
# import datetime
# import csv

# app = Flask(__name__)

# # Fonction pour enregistrer les données dans un fichier CSV (ou base de données)
# def log_scan(place, ip_address, scan_time, user_agent, referer, language):
#     with open('scans_log.csv', mode='a', newline='') as file:
#         writer = csv.writer(file)
#         writer.writerow([place, ip_address, scan_time, user_agent, referer, language])

# # Route pour capturer les scans des QR codes
# @app.route('/tracker', methods=['GET'])
# def tracker():
#     # Récupère le paramètre 'place' de l'URL
#     place = request.args.get('place')

#     # Récupère l'adresse IP du scanner
#     ip_address = request.remote_addr

#     # Enregistre l'heure du scan
#     scan_time = datetime.datetime.now()

#     # Récupère le User-Agent (navigateur et OS)
#     user_agent = request.headers.get('User-Agent')

#     # Récupère le referer (URL précédente)
#     referer = request.headers.get('Referer')

#     # Récupère la langue préférée de l'utilisateur
#     language = request.headers.get('Accept-Language')

#     # Enregistre les informations dans un fichier ou une base de données
#     log_scan(place, ip_address, scan_time, user_agent, referer, language)

#     # Redirige l'utilisateur vers Google après avoir enregistré les informations
#     return redirect("https://www.google.com", code=302)

# if __name__ == '__main__':
#     app.run(debug=True)
