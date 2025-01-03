import streamlit as st
import sqlite3
from fpdf import FPDF
from datetime import datetime
import pytz
import os

# Membuat koneksi ke database
conn = sqlite3.connect('pharmily.db')

# Membuat cursor untuk menjalankan query
cursor = conn.cursor()

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


def create_user(username, password, role, conn, hospital_name=None, hospital_address=None, hospital_contact=None, 
                doctor_name=None, doctor_sip=None, patient_name=None, patient_age=None, 
                patient_gender=None, patient_address=None):
    cursor = conn.cursor()

    # Debugging: Cek apakah tabel Users ada
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Users';")
    if cursor.fetchone() is None:
        print("Tabel 'Users' tidak ada!")
        return

    if role == 'dokter':
        cursor.execute('''INSERT INTO Users (username, password, role, hospital_name, hospital_address, hospital_contact, doctor_name, doctor_sip)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', 
                       (username, password, role, hospital_name, hospital_address, hospital_contact, doctor_name, doctor_sip))
    elif role == 'apotek':
        cursor.execute('''INSERT INTO Users (username, password, role) VALUES (?, ?, ?)''', (username, password, role))
    elif role == 'pasien':
        cursor.execute('''INSERT INTO Users (username, password, role, patient_name, patient_age, patient_gender, patient_address)
                          VALUES (?, ?, ?, ?, ?, ?, ?)''',
                       (username, password, role, patient_name, patient_age, patient_gender, patient_address))

    conn.commit()  # Pastikan perubahan disimpan
    print(f"User {username} dengan role {role} berhasil dibuat.")


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

def check_table_exists(conn, table_name):
    cursor = conn.cursor()
    cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
    return cursor.fetchone() is not None
def pilih_rumah_sakit_dan_dokter(conn, patient_id):
    cursor = conn.cursor()

    # Pilih rumah sakit dari daftar yang tersedia
    cursor.execute('''SELECT DISTINCT hospital_name FROM Users WHERE role = 'dokter' ''')
    hospitals = cursor.fetchall()

    hospital_names = [hospital[0] for hospital in hospitals]

    # Streamlit UI untuk memilih rumah sakit
    hospital_name = st.selectbox("Pilih Rumah Sakit", hospital_names)

    # Validasi rumah sakit yang dipilih
    cursor.execute('''SELECT id, doctor_name FROM Users WHERE hospital_name = ? AND role = 'dokter' ''', (hospital_name,))
    doctors = cursor.fetchall()

    if not doctors:
        st.error(f"Tidak ada dokter yang terdaftar di rumah sakit {hospital_name}.")
        return

    doctor_names = [doctor[1] for doctor in doctors]

    # Streamlit UI untuk memilih dokter
    doctor_name = st.selectbox("Pilih Dokter", doctor_names)

    # Validasi dokter yang dipilih
    cursor.execute('''SELECT id FROM Users WHERE doctor_name = ? AND hospital_name = ? AND role = 'dokter' ''',
                   (doctor_name, hospital_name))
    doctor_data = cursor.fetchone()

    if not doctor_data:
        st.error(f"Dokter {doctor_name} tidak ditemukan di rumah sakit {hospital_name}.")
        return

    doctor_id = doctor_data[0]

    # Generate nomor antrian
    queue_number = generate_queue_number(conn, doctor_id)

    # Menambahkan nomor antrian ke tabel QueueNumber
    add_queue_number(conn, patient_id, doctor_id)

    st.success(f"Nomor antrian Anda adalah: {queue_number}")


# Fungsi utama untuk membuat resep dan menampilkan tombol download PDF
def doctor_prescription_ui(conn, doctor_id, queue_number):
    # Ambil informasi dokter berdasarkan ID
    cursor = conn.cursor()
    cursor.execute(''' 
        SELECT doctor_name, doctor_sip, hospital_address, hospital_contact, hospital_name 
        FROM Users 
        WHERE id = ? AND role = 'dokter' 
    ''', (doctor_id,))
    hospital_info = cursor.fetchone()

    if not hospital_info:
        st.error("Dokter tidak ditemukan!")
        return

    # Ambil informasi pasien berdasarkan nomor antrian
    cursor.execute(''' 
        SELECT U.id, U.patient_name, U.patient_age, U.patient_gender, U.patient_address 
        FROM Users U 
        INNER JOIN QueueNumber Q ON U.id = Q.patient_id 
        WHERE Q.queue_number = ? 
    ''', (queue_number,))
    patient_info = cursor.fetchone()

    if not patient_info:
        st.error("Pasien tidak ditemukan!")
        return

    # Informasi dokter dan pasien
    patient_id, patient_name, patient_age, patient_gender, patient_address = patient_info
    st.write(f"Data Pasien: {patient_name}, {patient_age} tahun, {patient_gender}, {patient_address}")

    # Input resep oleh dokter
    prescriptions = input_prescriptions()
    timezone = pytz.timezone('Asia/Jakarta')
    created_at = datetime.now(timezone).strftime('%Y-%m-%d %H:%M:%S')

    # Membuat PDF resep
    pdf = DoctorPrescriptionPDF(
        hospital_name=hospital_info[4],
        doctor_name=hospital_info[0],
        doctor_sip=hospital_info[1],
        address=hospital_info[2],
        contact=hospital_info[3]
    )
    pdf.add_page()
    pdf.add_date_and_location(created_at)
    pdf.add_prescription_details(prescriptions)
    pdf.add_patient_info(patient_name, patient_gender, patient_age, patient_address)

    # Simpan PDF sementara
    folder = './temp_prescriptions'
    if not os.path.exists(folder):
        os.makedirs(folder)

    filename = f"{patient_name.replace(' ', '_')}_resep_dokter_{queue_number}.pdf"
    file_path = os.path.join(folder, filename)
    pdf.output(file_path)

    # Tampilkan tombol unduh di Streamlit
    with open(file_path, "rb") as pdf_file:
        pdf_data = pdf_file.read()
        st.download_button(
            label="Unduh Resep",
            data=pdf_data,
            file_name=filename,
            mime="application/pdf"
        )

    # Simpan data ke tabel PrescriptionPDF
    cursor.execute(''' 
        INSERT INTO PrescriptionPDF (pdf_filename, created_at, status) 
        VALUES (?, ?, 'Menunggu') 
    ''', (filename, created_at))
    conn.commit()

    st.success(f"Resep PDF telah dibuat dan disimpan dengan nama file: {filename}")

    # Meminta konfirmasi untuk membuat resep lagi
    create_another = st.radio("Apakah Anda ingin membuat resep lagi untuk pasien yang sama?", ("Ya", "Tidak"))
    if create_another == "Tidak":
        st.write("Selesai membuat resep untuk pasien ini.")

def apotek_dashboard(conn):
    st.title("Apotek Dashboard")

    cursor = conn.cursor()

    # Query untuk mendapatkan semua data dari tabel PrescriptionPDF
    query = '''
        SELECT id AS prescription_id,
               pdf_filename,
               created_at,
               status
        FROM PrescriptionPDF
        ORDER BY created_at DESC
    '''
    cursor.execute(query)
    prescriptions = cursor.fetchall()

    if prescriptions:
        st.subheader("Daftar Resep")

        # Membuat tabel
        for prescription in prescriptions:
            prescription_id = prescription[0]
            pdf_filename = prescription[1] if prescription[1] else "No PDF"
            created_at = prescription[2]
            status = prescription[3]

            st.markdown(f"#### Resep ID: {prescription_id}")
            st.write(f"**Nama File:** {pdf_filename}")
            st.write(f"**Tanggal Dibuat:** {created_at}")
            st.write(f"**Status:** {status}")

            # Path file PDF
            file_path = os.path.join("./temp_prescriptions", pdf_filename)

            if os.path.exists(file_path):
                # Tombol unduh
                with open(file_path, "rb") as pdf_file:
                    pdf_data = pdf_file.read()
                    st.download_button(
                        label="Unduh PDF",
                        data=pdf_data,
                        file_name=pdf_filename,
                        mime="application/pdf"
                    )
            else:
                st.warning(f"File PDF untuk Resep ID {prescription_id} tidak ditemukan!")

        # Opsi untuk memperbarui status resep
        st.subheader("Update Status Resep")
        with st.form("update_status_form"):
            prescription_id = st.number_input("Masukkan ID Resep", min_value=1, step=1)
            new_status = st.text_input("Masukkan Status Baru (e.g., Diproses, Selesai)")
            submit_button = st.form_submit_button("Update Status")

            if submit_button:
                # Validasi ID Resep
                cursor.execute('SELECT COUNT(*) FROM PrescriptionPDF WHERE id = ?', (prescription_id,))
                if cursor.fetchone()[0] == 0:
                    st.error("ID resep tidak ditemukan.")
                else:
                    # Perbarui status
                    cursor.execute(
                        'UPDATE PrescriptionPDF SET status = ? WHERE id = ?', 
                        (new_status, prescription_id)
                    )
                    conn.commit()
                    st.success(f"Status resep ID {prescription_id} telah diperbarui menjadi '{new_status}'.")

    else:
        st.warning("Tidak ada resep yang tersedia.")

# Fungsi untuk menangani signup pengguna (dokter, pasien, apotek)
def user_signup(conn, role):
    if role == "dokter":
        hospital_name = st.text_input("Hospital Name")
        hospital_address = st.text_input("Hospital Address")
        hospital_contact = st.text_input("Hospital Contact")
        doctor_name = st.text_input("Doctor Name")
        doctor_sip = st.text_input("Doctor SIP")
        username = st.text_input("Username (email)")
        password = st.text_input("Password", type="password")

        if st.button("Register as Doctor"):
            create_user(username, password, "dokter", conn, 
                        hospital_name=hospital_name, hospital_address=hospital_address, 
                        hospital_contact=hospital_contact, doctor_name=doctor_name, doctor_sip=doctor_sip)
            st.success("Doctor registered successfully!")

    elif role == "pasien":
        patient_name = st.text_input("Patient Name")
        patient_age = st.number_input("Patient Age", min_value=1)
        patient_gender = st.selectbox("Patient Gender", ["Laki-laki", "Perempuan"])
        patient_address = st.text_area("Patient Address")
        username = st.text_input("Username (email)")
        password = st.text_input("Password", type="password")

        if st.button("Register as Patient"):
            create_user(conn, username, password, "pasien", 
                        patient_name=patient_name, patient_age=patient_age, 
                        patient_gender=patient_gender, patient_address=patient_address)
            st.success("Patient registered successfully!")

    elif role == "apotek":
        username = st.text_input("Username (email)")
        password = st.text_input("Password", type="password")

        if st.button("Register as Pharmacy"):
            create_user(conn, username, password, "apotek")
            st.success("Pharmacy registered successfully!")

    else:
        st.error("Invalid role!")

# Fungsi untuk autentikasi pengguna (login)
def authenticate_user(conn, username, password, role):
    cursor = conn.cursor()
    cursor.execute('''SELECT * FROM Users WHERE username = ? AND password = ? AND role = ?''', (username, password, role))
    user = cursor.fetchone()
    return user

# Fungsi login pengguna
def user_login(conn):
    username = st.text_input("Username (email)")
    password = st.text_input("Password", type="password")
    role = st.selectbox("Role", ["dokter", "pasien", "apotek"])

    if st.button("Login"):
        user = authenticate_user(conn, username, password, role)

        if user:
            st.success(f"Login successful as {role}!")
            return user
        else:
            st.error("Login failed. Check your credentials.")
            return None
        
def main():
    conn = sqlite3.connect("pharmily.db")
    # Memastikan tabel-tabel yang diperlukan ada
    create_tables(conn)

    st.title("Pharmily")
    menu = st.sidebar.radio("Pilih Opsi", ["Sign Up", "Login", "Keluar"])

    if menu == "Sign Up":
        role = st.selectbox("Pilih Role", ["dokter", "pasien", "apotek"])
        user_signup(conn, role)

    elif menu == "Login":
        user = user_login(conn)
        if user:
            if user[3] == "pasien":
                st.write("Pilih rumah sakit dan dokter...")
                pilih_rumah_sakit_dan_dokter(conn, user[0])  # Adjust logic
            elif user[3] == "dokter":
                st.write("Memulai pembuatan resep...")
                nomor_antrian = st.text_input("Masukkan nomor antrian pasien")
                # Add logic to create prescriptions for doctors
            elif user[3] == "apotek":
                st.write("DASHBOARD APOTEK")
                apotek_dashboard(conn)

    elif menu == "Keluar":
        st.write("Keluar dari aplikasi.")
        st.stop()

if __name__ == "__main__":
    main()


