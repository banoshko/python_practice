import smtplib as smtp

sender = "richie.vajko@gmail.com"
password = "hnyl jarb mbbl fixd"

#
reciever = "flachbartfilip@gmail.com"
message = "Fildovi"
#

count = 0

final = 10

while count != final:
    server = smtp.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(sender, password)
    server.sendmail(sender, reciever, message)
    server.quit()
    count +=1

print("Email sent")