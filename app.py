from flask import Flask, render_template, request, redirect, session, send_file
import mysql.connector
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import io

app = Flask(__name__)
app.secret_key = 'psikotest'

# ================= DATABASE =================
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="psikotest"
)

def admin_required(f):
    def wrap(*args, **kwargs):
        if 'id_admin' not in session:
            return redirect('/login_admin/')
        return f(*args, **kwargs)
    wrap.__name__ = f.__name__
    return wrap


def siswa_required(f):
    def wrap(*args, **kwargs):
        if 'id_siswa' not in session:
            return redirect('/login_siswa/')
        return f(*args, **kwargs)
    wrap.__name__ = f.__name__
    return wrap


# ================= HELPER =================
def get_penjelasan(kategori, skor):
    if skor >= 80:
        return f"Kemampuan {kategori} kamu sangat baik."
    elif skor >= 60:
        return f"Kemampuan {kategori} kamu tergolong baik."
    elif skor >= 40:
        return f"Kemampuan {kategori} kamu cukup."
    else:
        return f"Kemampuan {kategori} kamu masih rendah."

# ================= HOME =================
@app.route('/')
def home():
    return render_template('home.html')

# ================= LOGIN SISWA =================
@app.route('/login_siswa/', methods=['GET', 'POST'])
def login_siswa():
    if request.method == 'POST':
        nis = request.form['nis']
        password = request.form['password']

        cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM tb_siswa WHERE nis=%s AND password=%s", (nis, password))
        siswa = cur.fetchone()
        cur.close()

        if siswa:
            session.clear()
            session['id_siswa'] = siswa['id_siswa']
            return redirect('/dashboard_siswa/')
        else:
            return render_template('login_siswa.html', error="NIS atau password salah")

    return render_template('login_siswa.html')

# ================= LOGIN ADMIN =================
@app.route('/login_admin/', methods=['GET', 'POST'])
def login_admin():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM tb_admin WHERE username=%s AND password=%s",
                    (username, password))
        admin = cur.fetchone()
        cur.close()

        if admin:
            session.clear()
            session['id_admin'] = admin['id_admin']
            return redirect('/dashboard_admin/')
        else:
            return render_template('login_admin.html', error="Login admin gagal")

    return render_template('login_admin.html')

# ================= DASHBOARD SISWA =================
@app.route('/dashboard_siswa/')
def dashboard_siswa():
    if 'id_siswa' not in session:
        return redirect('/login_siswa/')

    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT k.id_kategori, k.nama_kategori,
        CASE WHEN EXISTS (
            SELECT 1 FROM tb_hasil h
            WHERE h.id_siswa=%s AND h.id_kategori=k.id_kategori
        ) THEN 1 ELSE 0 END AS sudah_dikerjakan
        FROM tb_kategori k
    """, (session['id_siswa'],))
    kategori = cur.fetchall()
    cur.close()

    return render_template('dashboard_siswa.html', kategori=kategori)

# ================= TES SISWA =================
@app.route('/tes/<int:id_kategori>/', methods=['GET', 'POST'])
def tes(id_kategori):
    if 'id_siswa' not in session:
        return redirect('/login_siswa/')

    cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM tb_soal WHERE id_kategori=%s", (id_kategori,))
    soal = cur.fetchall()

    if request.method == 'POST':
        benar = 0
        for s in soal:
            jawaban = request.form.get(str(s['id_soal']))
            if jawaban == s['kunci_jawaban']:
                benar += 1

        skor = benar * 5
        interpretasi = "Baik" if skor >= 70 else "Perlu Latihan"

        cur.execute("""
            INSERT INTO tb_hasil (id_siswa, id_kategori, skor, interpretasi)
            VALUES (%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
            skor=VALUES(skor), interpretasi=VALUES(interpretasi)
        """, (session['id_siswa'], id_kategori, skor, interpretasi))

        db.commit()
        cur.close()
        return redirect('/hasil/')

    cur.close()
    return render_template('kerjakan_tes.html', soal=soal)

# ================= HASIL SISWA =================
@app.route('/hasil/')
def hasil():
    if 'id_siswa' not in session:
        return redirect('/login_siswa/')

    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT k.nama_kategori, h.skor, h.interpretasi
        FROM tb_hasil h
        JOIN tb_kategori k ON h.id_kategori=k.id_kategori
        WHERE h.id_siswa=%s
    """, (session['id_siswa'],))
    hasil = cur.fetchall()
    cur.close()

    for h in hasil:
        h['penjelasan'] = get_penjelasan(h['nama_kategori'], h['skor'])

    return render_template('hasil.html', hasil=hasil)

# ================= DOWNLOAD PDF =================
@app.route('/download_pdf/')
def download_pdf():
    if 'id_siswa' not in session:
        return redirect('/login_siswa/')

    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT k.nama_kategori, h.skor, h.interpretasi
        FROM tb_hasil h
        JOIN tb_kategori k ON h.id_kategori=k.id_kategori
        WHERE h.id_siswa=%s
    """, (session['id_siswa'],))
    hasil = cur.fetchall()
    cur.close()

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    y = 800

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, y, "Hasil Psikotes")
    y -= 40

    pdf.setFont("Helvetica", 12)
    for h in hasil:
        pdf.drawString(50, y, f"{h['nama_kategori']} : {h['skor']} ({h['interpretasi']})")
        y -= 20

    pdf.save()
    buffer.seek(0)

    return send_file(buffer, as_attachment=True,
                     download_name="hasil_psikotes.pdf",
                     mimetype="application/pdf")

# ================= DASHBOARD ADMIN =================
@app.route('/dashboard_admin/')
@admin_required
def dashboard_admin():
    cur = db.cursor(dictionary=True)

    cur.execute("SELECT COUNT(*) AS total FROM tb_siswa")
    total_siswa = cur.fetchone()['total']

    cur.execute("SELECT COUNT(DISTINCT id_siswa) AS sudah FROM tb_hasil")
    sudah_tes = cur.fetchone()['sudah']

    belum_tes = total_siswa - sudah_tes

    cur.execute("SELECT AVG(skor) AS rata FROM tb_hasil")
    rata = cur.fetchone()['rata']
    rata_skor = int(rata) if rata else 0

    cur.close()

    return render_template(
        'dashboard_admin.html',
        total_siswa=total_siswa,
        sudah_tes=sudah_tes,
        belum_tes=belum_tes,
        rata_skor=rata_skor
    )


# ================= ADMIN LIHAT HASIL =================
@app.route('/admin/hasil/')
@admin_required
def admin_hasil():
    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT s.nis, s.nama,
               k.nama_kategori,
               h.skor, h.interpretasi
        FROM tb_hasil h
        JOIN tb_siswa s ON h.id_siswa=s.id_siswa
        JOIN tb_kategori k ON h.id_kategori=k.id_kategori
        ORDER BY s.nama
    """)
    data = cur.fetchall()
    cur.close()

    return render_template('admin_hasil.html', data=data)


# admin siswa dan jawaban 
@app.route('/admin/siswa/')
@admin_required
def admin_siswa():
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT nis, nama FROM tb_siswa")
    siswa = cur.fetchall()
    cur.close()

    return render_template('admin_siswa.html', siswa=siswa)

@app.route('/admin/jawaban/<int:id_siswa>/')
@admin_required
def admin_jawaban(id_siswa):
    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT s.nama, so.soal, j.jawaban
        FROM tb_jawaban j
        JOIN tb_soal so ON j.id_soal = so.id_soal
        JOIN tb_siswa s ON j.id_siswa = s.id_siswa
        WHERE j.id_siswa=%s
    """, (id_siswa,))
    jawaban = cur.fetchall()
    cur.close()

    return render_template('admin_jawaban.html', jawaban=jawaban)

#admin kategori
@app.route('/admin/kategori/')
@admin_required
def admin_kategori():
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM tb_kategori")
    kategori = cur.fetchall()
    cur.close()

    return render_template('admin_kategori.html', kategori=kategori)

#admin jawaban
@app.route('/admin/jawaban/')
@admin_required
def admin_jawaban_list():
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT id_siswa, nis, nama FROM tb_siswa")
    siswa = cur.fetchall()
    cur.close()

    return render_template('admin_jawaban_list.html', siswa=siswa)

# ================= LOGOUT =================
@app.route('/logout/')
def logout():
    session.clear()
    return redirect('/')

# ================= RUN =================
if __name__ == '__main__':
    app.run(debug=True)
