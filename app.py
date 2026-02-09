from flask import Flask, render_template, request, redirect, session, send_file
import mysql.connector
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import io

app = Flask(__name__)
app.secret_key = 'psikotest'

# DATABASE
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="psikotest"
)

# ================= HELPER =================
def get_penjelasan(kategori, skor):
    if skor >= 80:
        return f"Kemampuan {kategori} kamu sangat baik. Kamu mampu menyelesaikan soal sulit dengan konsisten."
    elif skor >= 60:
        return f"Kemampuan {kategori} kamu tergolong baik, namun masih perlu ditingkatkan."
    elif skor >= 40:
        return f"Kemampuan {kategori} kamu cukup, tapi masih sering ragu atau kurang teliti."
    else:
        return f"Kemampuan {kategori} kamu masih rendah. Disarankan banyak latihan soal dasar."

# ================= LOGIN =================
@app.route('/login_siswa/', methods=['GET', 'POST'])
def login_siswa():
    if request.method == 'POST':
        nis = request.form['nis']
        password = request.form['password']

        print(nis, password)  # buat tes

        return redirect('/dashboard')

    return render_template('login_siswa.html')


# ================= DASHBOARD =================
@app.route('/dashboard_siswa/')
def dashboard_siswa():
    if 'id_siswa' not in session:
        return redirect('/login_siswa')

    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT 
            k.id_kategori,
            k.nama_kategori,
            k.deskripsi,
            CASE 
                WHEN EXISTS (
                    SELECT 1 FROM tb_hasil h
                    WHERE h.id_siswa=%s AND h.id_kategori=k.id_kategori
                ) THEN 1
                ELSE 0
            END AS sudah_dikerjakan
        FROM tb_kategori k
    """, (session['id_siswa'],))
    kategori = cur.fetchall()
    cur.close()

    return render_template('dashboard_siswa.html', kategori=kategori)

# ================= TES =================
@app.route('/tes/<int:id_kategori>/', methods=['GET','POST'])
def tes(id_kategori):
    if 'id_siswa' not in session:
        return redirect('/login_siswa')

    cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM tb_soal WHERE id_kategori=%s LIMIT 20", (id_kategori,))
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
                skor=VALUES(skor),
                interpretasi=VALUES(interpretasi)
        """, (session['id_siswa'], id_kategori, skor, interpretasi))

        db.commit()
        cur.close()
        return redirect('/hasil')

    cur.close()
    return render_template('kerjakan_tes.html', soal=soal)

# ================= RESET TES =================
@app.route('/reset_tes/<int:id_kategori>')
def reset_tes(id_kategori):
    cur = db.cursor()
    cur.execute(
        "DELETE FROM tb_hasil WHERE id_siswa=%s AND id_kategori=%s",
        (session['id_siswa'], id_kategori)
    )
    db.commit()
    cur.close()
    return redirect(f'/tes/{id_kategori}')

# ================= HASIL =================
@app.route('/hasil/')
def hasil():
    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT k.nama_kategori, h.skor, h.interpretasi
        FROM tb_hasil h
        JOIN tb_kategori k ON h.id_kategori=k.id_kategori
        WHERE h.id_siswa=%s
    """, (session['id_siswa'],))
    hasil = cur.fetchall()

    for h in hasil:
        h['penjelasan'] = get_penjelasan(h['nama_kategori'], h['skor'])

    cur.close()
    return render_template('hasil.html', hasil=hasil)

# ================= PDF =================
@app.route('/download_pdf/')
def download_pdf():
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
        pdf.drawString(50, y, f"{h['nama_kategori']} : {h['skor']} - {h['interpretasi']}")
        y -= 20

    pdf.save()
    buffer.seek(0)

    return send_file(buffer, as_attachment=True,
                     download_name="hasil_psikotes.pdf",
                     mimetype="application/pdf")

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True, use_reloader=False)