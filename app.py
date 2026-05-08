import os
import uuid
import boto3
import pymysql
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, flash

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'kunci_rahasia_lokal')

# --- Konfigurasi AWS & Database dari Environment Variables ---
S3_BUCKET = os.getenv('S3_BUCKET_NAME', 'nama-bucket-s3-anda')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_USER = os.getenv('DB_USER', 'root')
DB_PASS = os.getenv('DB_PASS', '')
DB_NAME = os.getenv('DB_NAME', 'layanandesa')
CF_DOMAIN = os.getenv('CLOUDFRONT_DOMAIN', '')

# Inisialisasi S3 Client
s3 = boto3.client('s3')

# Fungsi Koneksi RDS (MySQL)
def get_db_connection():
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor
    )

# Inisialisasi Tabel di MySQL
def init_mysql_db():
    try:
        # 1. Masuk ke RDS TANPA nama database untuk membuat databasenya dulu
        koneksi_awal = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASS
        )
        with koneksi_awal.cursor() as c:
            # Buat database jika belum ada
            c.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
        koneksi_awal.commit()
        koneksi_awal.close()

        # 2. Setelah database ada, masuk secara normal untuk membuat tabel
        conn = get_db_connection()
        with conn.cursor() as c:
            c.execute('''CREATE TABLE IF NOT EXISTS pengajuan (
                            id_tracking VARCHAR(50) PRIMARY KEY, 
                            nama VARCHAR(150), 
                            nik VARCHAR(50), 
                            jenis VARCHAR(100), 
                            file_ktp VARCHAR(255), 
                            status VARCHAR(50)
                         )''')
            c.execute('''CREATE TABLE IF NOT EXISTS pengaduan (
                            id_laporan VARCHAR(50) PRIMARY KEY, 
                            nama VARCHAR(150), 
                            kategori VARCHAR(100), 
                            deskripsi TEXT, 
                            file_bukti VARCHAR(255)
                         )''')
        conn.commit()
        conn.close()
        print("Database dan tabel berhasil diinisialisasi!")
    except Exception as e:
        print(f"Gagal inisialisasi database: {e}")

init_mysql_db()

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
        
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            s3_filename = f"pengajuan/{uuid.uuid4().hex[:8]}_{filename}"
            
            # Upload ke Amazon S3
            s3.upload_fileobj(file, S3_BUCKET, s3_filename)
            
            id_tracking = str(uuid.uuid4())[:8].upper()
            status = "Menunggu Verifikasi"
            
            # Simpan ke Amazon RDS
            conn = get_db_connection()
            with conn.cursor() as c:
                c.execute("INSERT INTO pengajuan (id_tracking, nama, nik, jenis, file_ktp, status) VALUES (%s, %s, %s, %s, %s, %s)", 
                          (id_tracking, nama, nik, jenis, s3_filename, status))
            conn.commit()
            conn.close()
            
            flash(f'Pengajuan berhasil! ID Tracking Anda: {id_tracking}')
            return redirect(url_for('status_layanan'))
            
    return render_template('pengajuan.html')

# --- Route Pengaduan Masyarakat ---
@app.route('/pengaduan', methods=['GET', 'POST'])
def pengaduan():
    if request.method == 'POST':
        nama = request.form['nama']
        kategori = request.form['kategori']
        deskripsi = request.form['deskripsi']
        file = request.files['file_bukti']
        
        s3_filename = ""
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            s3_filename = f"pengaduan/{uuid.uuid4().hex[:8]}_{filename}"
            
            # Upload ke Amazon S3
            s3.upload_fileobj(file, S3_BUCKET, s3_filename)
            
        id_laporan = "LAP-" + str(uuid.uuid4())[:6].upper()
        
        # Simpan ke Amazon RDS
        conn = get_db_connection()
        with conn.cursor() as c:
            c.execute("INSERT INTO pengaduan (id_laporan, nama, kategori, deskripsi, file_bukti) VALUES (%s, %s, %s, %s, %s)", 
                      (id_laporan, nama, kategori, deskripsi, s3_filename))
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
        
        # Ambil data dari Amazon RDS
        conn = get_db_connection()
        with conn.cursor() as c:
            c.execute("SELECT * FROM pengajuan WHERE id_tracking=%s", (id_tracking,))
            data = c.fetchone()
        conn.close()
        
        if not data:
            flash('ID Tracking tidak ditemukan.')
            
    return render_template('status.html', data=data, cf_domain=CF_DOMAIN)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)