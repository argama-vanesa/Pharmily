import sqlite3
from fpdf import FPDF
from datetime import datetime
import pytz
import os


def create_database():
    db_name = "pharmily.db"
    if not os.path.exists(db_name):
        conn = sqlite3.connect(db_name)
        create_tables(conn)
        conn.close()
        print(f"Database {db_name} dan tabel telah dibuat.")
    else:
        print(f"Database {db_name} sudah ada.")

def create_tables(conn):
    cursor = conn.cursor()
    # Membuat tabel Users
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,  -- Gunakan hash password untuk keamanan
            role TEXT NOT NULL,  -- "dokter", "apotek", "pasien"
            hospital_name TEXT,  -- Nama rumah sakit (hanya untuk dokter)
            hospital_address TEXT,  -- Alamat rumah sakit (hanya untuk dokter)
            hospital_contact TEXT,  -- Kontak rumah sakit (hanya untuk dokter)
            doctor_sip TEXT,  -- Hanya untuk dokter
            doctor_name TEXT,  -- Hanya untuk dokter
            patient_name TEXT,  -- Hanya untuk pasien
            patient_age INTEGER,  -- Hanya untuk pasien
            patient_gender TEXT,  -- Hanya untuk pasien
            patient_address TEXT  -- Hanya untuk pasien
        )
    ''')

    # Membuat tabel PrescriptionPDF
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS PrescriptionPDF (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pdf_filename TEXT NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Menunggu'
        )
    ''')

    # Membuat tabel QueueNumber
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS QueueNumber (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            doctor_id INTEGER NOT NULL,
            queue_number TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(patient_id) REFERENCES Users(id),
            FOREIGN KEY(doctor_id) REFERENCES Users(id)
        )
    ''')

    conn.commit()


# Jalankan fungsi untuk membuat database baru
if __name__ == "__main__":
    create_database()

# Fungsi untuk memasukkan data pengguna (dokter, pasien, apotek)
def create_user(conn, username, password, role, hospital_name=None, hospital_address=None, hospital_contact=None, 
                doctor_name=None, doctor_sip=None, patient_name=None, patient_age=None, 
                patient_gender=None, patient_address=None):
    cursor = conn.cursor()

    # Menyusun data untuk pengguna
    cursor.execute(''' 
    INSERT INTO Users (username, password, role, hospital_name, hospital_address, hospital_contact, doctor_name, doctor_sip, 
                       patient_name, patient_age, patient_gender, patient_address)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (username, password, role, hospital_name, hospital_address, hospital_contact, doctor_name, doctor_sip, 
          patient_name, patient_age, patient_gender, patient_address))

    conn.commit()
    return cursor.lastrowid

# Fungsi untuk membuat nomor antrian berdasarkan jumlah pasien saat ini
def generate_queue_number(conn, doctor_id):
    cursor = conn.cursor()
    cursor.execute('''SELECT COUNT(*) FROM QueueNumber WHERE doctor_id = ?''', (doctor_id,))
    count = cursor.fetchone()[0]
    return f"{doctor_id}-{count + 1:02d}"

def add_queue_number(conn, patient_id, doctor_id):
    cursor = conn.cursor()
    queue_number = generate_queue_number(conn, doctor_id)
    created_at = datetime.now(pytz.timezone('Asia/Jakarta')).strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute('''
        INSERT INTO QueueNumber (patient_id, doctor_id, queue_number, created_at)
        VALUES (?, ?, ?, ?)
    ''', (patient_id, doctor_id, queue_number, created_at))
    conn.commit()
    print(f"Nomor antrian {queue_number} telah ditambahkan ke tabel QueueNumber.")


# Kelas untuk membuat file PDF resep
class DoctorPrescriptionPDF(FPDF):
    def __init__(self, hospital_name=None, doctor_name=None, doctor_sip=None, address=None, contact=None, **kwargs):
        super().__init__(**kwargs)
        self.hospital_name = hospital_name
        self.doctor_name = doctor_name
        self.doctor_sip = doctor_sip
        self.address = address
        self.contact = contact

    def header(self):
        if self.hospital_name:
            self.set_font('Times', 'B', 16)
            self.cell(0, 10, f'{self.hospital_name}', ln=True, align='C')
            self.set_font('Times', 'B', 12)
            self.cell(0, 8, f'Dokter: {self.doctor_name} | SIP: {self.doctor_sip}', ln=True, align='C')
            self.cell(0, 8, f'Alamat: {self.address}', ln=True, align='C')
            self.cell(0, 8, f'Kontak: {self.contact}', ln=True, align='C')
            self.ln(5)
            self.cell(0, 0, '', 'T', 1, 'C')  # Garis horizontal
            self.ln(5)

    def add_date_and_location(self, created_at):
        # Meminta input lokasi dari user
        location = input("Masukkan lokasi (kota atau alamat lengkap): ")

        self.set_y(50)  # Tepat di bawah header
        self.set_x(-70)  # Geser ke kanan (pojok kanan atas)
        self.set_font('Times', 'I', 12)
        self.cell(0, 10, f'{location}, {created_at}', ln=True, align='R')

    def add_prescription_details(self, prescriptions):
        self.set_y(70)  # Mulai di tengah halaman
        self.ln(5)
        self.set_font('Times', '', 12)
        for prescription in prescriptions:
            self.cell(0, 10, f'R/ {prescription["nama obat"]}, {prescription["bentuk sediaan"]}, {prescription["wadah penyimpanan"]}, {prescription["jumlah obat"]}', ln=True, align='C')
            self.cell(0, 10, f'S {prescription["frekuensi"]} {prescription["takaran"]} {prescription["keterangan"]}', ln=True, align='C')
            self.ln(5)
            self.cell(0, 0, '', 'T', 1, 'C')  # Garis horizontal
            self.ln(5)

    def add_patient_info(self, patient_name, patient_gender, patient_age, patient_address):
        self.set_y(200)  # Posisikan di bagian bawah halaman
        self.set_font('Times', '', 12)
        self.ln(5)
        self.cell(0, 0, '', 'T', 1, 'C')  # Garis horizontal
        self.ln(5)
        self.cell(0, 10, f'Nama            : {patient_name}', ln=True, align='L')
        self.cell(0, 10, f'Jenis Kelamin: {patient_gender}', ln=True, align='L')
        self.cell(0, 10, f'Umur        : {patient_age} tahun', ln=True, align='L')
        self.cell(0, 10, f'Alamat      : {patient_address}', ln=True, align='L')

    def add_footer(self, hospital_name, doctor_name):
        self.set_y(-30)
        self.set_font('Times', 'I', 12)
        self.cell(0, 10, f'{hospital_name} - {doctor_name}', 0, 0, 'C')


# Fungsi input data resep
def input_prescriptions():
    prescriptions = []
    n = int(input("Masukkan jumlah bentuk sediaan yang akan diresepkan: "))
    for i in range(n):
        nama_obat = input("Masukkan nama obat (secara lengkap) : ")
        bentuk_sediaan = input("Masukkan bentuk sediaan (boleh disingkat):")
        wadah_penyimpanan = input("Masukkan wadah penyimpanan obatnya (boleh disingkat):")
        jumlah_obat = input("Masukkan jumlah obat yang akan diterima pasien (wajib gunakan angka romawi): ")
        frekuensi = input("Masukkan frekuensi penggunaan obat (wajib gunakan angka biasa) dan satuannya (contoh 2 dd): ")
        takaran = input("Masukkan takaran satu kali pemberian obat (termasuk satuan, misal cth I): ")
        keterangan = input("Silahkan tambahkan keterangan jika ada : ")
        prescriptions.append({
            'nama obat': nama_obat,
            'bentuk sediaan': bentuk_sediaan,
            'wadah penyimpanan': wadah_penyimpanan,
            'jumlah obat': jumlah_obat,
            'frekuensi': frekuensi,
            'takaran': takaran,
            'keterangan': keterangan,
        })
    return prescriptions