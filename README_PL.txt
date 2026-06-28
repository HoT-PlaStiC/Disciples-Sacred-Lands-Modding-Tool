*************************************
DBI codec for Disciples Sacred Lands
*************************************
-------------------
made by HoT_PlaStiC
-------------------

Ten skrypt umożliwia:

    1. wyświetlenie listy obrazów z dowolnego pliku .DBI
    2. dekodowanie obrazów z dowolnego pliku .DBI
    3. kodowanie obrazów do dowolnego pliku .DBI
    4. zastępowanie obrazów w dowolnym pliku .DBI

Najpierw uruchom PowerShell (wpisz “powershell” w bieżącym katalogu i
naciśnij Enter).

Aby skrypt działał, musisz mieć zainstalowaną bibliotekę Pillow.

Wpisz:

python -m pip install pillow

i naciśnij Enter.

    1. Wyświetlenie listy obrazów:
            python fd_portrait_codec_v2_36.py list any.DBI

    2. Dekodowanie obrazów z dowolnego pliku .DBI:
            python fd_portrait_codec_v2_36.py decode any.DBI portrék\

        Dekodowanie wszystkich obrazów ze wszystkich plików .DBI:
            python fd_portrait_codec_v2_36.py decodeall

    (Możesz zmienić nazwę folderu (portrék\), a także zastąpić any.DBI
    plikiem any_mod.DBI, jeśli chcesz dekodować wcześniej zakodowane obrazy.)

    3. Kodowanie obrazów:

        Dla UNIT.DBI:
            python fd_portrait_codec_v2_36.py encode CFDW0048.png UNIT.DBI

    (CFDW0048.png jest tylko przykładowym plikiem.)

    (Podczas kodowania do UNIT.DBI obrazy muszą mieć rozmiar
    55x67 lub 115x67 pikseli i być zapisane w formacie PNG.)

    (Podczas kodowania nowego obrazu do UNIT.DBI skrypt automatycznie
    utworzy nowy slot i nowy kod (od GP001S00),
    dlatego nie trzeba podawać nazwy na końcu polecenia.)

    Aby nadpisać oryginalny plik .DBI, dodaj flagę "ow":

            python fd_portrait_codec_v2_36.py encode CFDW0048.png UNIT.DBI ow

        Dla pozostałych plików .DBI:
            python fd_portrait_codec_v2_36.py encode CFDW0048.png any.DBI FD050S00

    (CFDW0048.png jest tylko przykładem.)

    (Należy podać nazwę obrazu. FD050S00 jest jedynie przykładem.)

    Uwaga: gra wykorzystuje system warstw,
    dlatego nazwa określa kategorię warstwy obrazu.
    Użyj właściwej nazwy.

    Aby nadpisać oryginalny plik .DBI, dodaj flagę "ow":

            python fd_portrait_codec_v2_36.py encode CFDW0048.png any.DBI FD050S00 ow

    4. Zastępowanie obrazów:
            python fd_portrait_codec_v2_36.py replace CFDW0048.png any.DBI FD026S00

    (CFDW0048.png jest tylko przykładem.)

    (Podczas pracy z UNIT.DBI obrazy muszą mieć rozmiar
    55x67 lub 115x67 pikseli i być zapisane w formacie PNG.)

    (Możesz wybrać, który oryginalny portret chcesz zastąpić
    (na przykład FD026S00).)

    Aby nadpisać oryginalny plik .DBI, dodaj flagę "ow":

            python fd_portrait_codec_v2_36.py replace CFDW0048.png any.DBI FD026S00 ow

Po zakończeniu kodowania skrypt utworzy plik any_mod.DBI, który można
skopiować do katalogu Imgs1, Imgs2 lub Interf gry Disciples Sacred
Lands, zmienić jego nazwę na any.DBI i zastąpić nim oryginalny plik
(przed wykonaniem tej operacji zaleca się utworzenie kopii zapasowej).
