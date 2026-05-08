import os
import sqlite3
import uuid
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, flash

app = Flask(__name__)
app.secret_key = 'kunci_rahasia_lokal'

UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Update Database untuk menambahkan tabel pengaduan
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    # Tabel Pengajuan (Sudah ada sebelumnya)
    c.execute('''CREATE TABLE IF NOT EXISTS pengajuan
                 (id_tracking TEXT PRIMARY KEY, nama TEXT, nik TEXT, jenis TEXT, file_ktp TEXT, status TEXT)''')
    # Tabel Pengaduan (Baru)
    c.execute('''CREATE TABLE IF NOT EXISTS pengaduan
                 (id_laporan TEXT PRIMARY KEY, nama TEXT, kategori TEXT, deskripsi TEXT, file_bukti TEXT)''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

# --- Route Pengajuan Surat ---
@app.route('/pengajuan', methods=['GET', 'POST'])
def pengajuan():
    if request.method == 'POST':
        nama = request.form['nama']
        nik = request.form['nik']
        jenis = request.form['jenis']
        file = request.files['file_ktp']
        
        if file:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path) # TODO AWS: Ganti ke boto3 upload S3
            
            id_tracking = str(uuid.uuid4())[:8].upper()
            status = "Menunggu Verifikasi"
            
            conn = sqlite3.connect('database.db') # TODO AWS: Ganti ke RDS
            c = conn.cursor()
            c.execute("INSERT INTO pengajuan VALUES (?, ?, ?, ?, ?, ?)", 
                      (id_tracking, nama, nik, jenis, filename, status))
            conn.commit()
            conn.close()
            
            flash(f'Pengajuan berhasil! ID Tracking Anda: {id_tracking}')
            return redirect(url_for('status_layanan'))
            
    return render_template('pengajuan.html')

# --- Route Pengaduan Masyarakat (Baru) ---
@app.route('/pengaduan', methods=['GET', 'POST'])
def pengaduan():
    if request.method == 'POST':
        nama = request.form['nama']
        kategori = request.form['kategori']
        deskripsi = request.form['deskripsi']
        file = request.files['file_bukti']
        
        filename = ""
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path) # TODO AWS: Ganti ke boto3 upload S3 [cite: 38]
            
        id_laporan = "LAP-" + str(uuid.uuid4())[:6].upper()
        
        conn = sqlite3.connect('database.db') # TODO AWS: Ganti ke koneksi RDS [cite: 37]
        c = conn.cursor()
        c.execute("INSERT INTO pengaduan VALUES (?, ?, ?, ?, ?)", 
                  (id_laporan, nama, kategori, deskripsi, filename))
        conn.commit()
        conn.close()
        
        flash(f'Pengaduan berhasil dikirim! ID Laporan Anda: {id_laporan}. Terima kasih atas partisipasi Anda.')
        return redirect(url_for('index'))
            
    return render_template('pengaduan.html')

# --- Route Status Layanan ---
@app.route('/status', methods=['GET', 'POST'])
def status_layanan():
    data = None
    if request.method == 'POST':
        id_tracking = request.form['id_tracking']
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT * FROM pengajuan WHERE id_tracking=?", (id_tracking,))
        data = c.fetchone()
        conn.close()
        
        if not data:
            flash('ID Tracking tidak ditemukan.')
            
    return render_template('status.html', data=data)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)