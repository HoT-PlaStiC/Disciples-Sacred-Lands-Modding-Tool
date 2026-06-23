*************************************
DBI codec for Disciples Sacred Lands
*************************************
-------------------
made by HoT_PlaStiC
-------------------


This script will enable to 

	1., list unit portraits from UNIT.DBI
	2., decode unit portraits from UNIT.DBI
	3., encode images into UNIT.DBI


First use powershell (type powershell into directory and press enter)

In order to work you have to have pillow installed:

type:

python -m pip install pillow

enter


	1., list units:
	type: python fd_portrait_codec_v2_10.py list UNIT.DBI IMGGRAB.BIN


	2., decode unit portraits:
	type: python fd_portrait_codec_v2_10.py decode UNIT.DBI portrék\ IMGGRAB.BIN

	(you can change the folder name (portrék\) also you can change UNIT.DBI
	to UNIT_mod.DBI if you would like to decode the encoded images)


	3., encode images:
	type: python fd_portrait_codec_v2_10.py encode CFDW0048.png UNIT.DBI IMGGRAB.BIN

	(you can write your custom images here (CFDW0048.png is a sample image)
	Images should be 55x67 or 115x67 scaled)

	(if you encode a new image it will automatically generate a new slot and code for it
	(starting with GP001S00))

	4., replace images:
	python fd_portrait_codec_v2_10.py replace CFDW0048.png UNIT.DBI FD026S00 IMGGRAB.BIN

	(you can write your custom images here (CFDW0048.png is a sample image)
	Images should be 55x67 or 115x67 scaled)
	(you can choose which original portrait you would like to replace (FD026S00 for example)


	After you encode, the script will generate an UNIT_mod.DBI file, which you can copy
	and paste into Disciples Sacred Lands Imgs1 directory, and rename it to UNIT.DBI 
	overwrite the original (make backup first!)


IMGGRAB.BIN was used from dsl-unpacker made by HSerg
