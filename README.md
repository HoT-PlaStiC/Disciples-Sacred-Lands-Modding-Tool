# Disciples-Sacred-Lands-Modding-Tool

Decoding and Encoding in Disciples Sacred Lands (image and animation and sound)
-----------------------------------------------------------------------------------
DBF Editor for Disciples Sacred Lands (second tab)
-----------------------------------------------------------------------------------
Building Editor for Disciples Sacred Lands (third tab)
-----------------------------------------------------------------------------------

Current version: 3.23
*********************************************

3.23: Made some more building structure available for structure generator, Capital Screen Layers no longer can have negative value,
Layer field now clamps to the closest available value instead of error box, when written manually,
Diplomat title changed to Guildmaster in DBF Editor (as it is in game), Generate Remaining Chain Button removed, as it no longer makes sense,
Encoding in UNIT.DBI will no longer auto-generate the same number for small and large portraits to avoid pairing with not proper images.
Baseline/Reset/Load popup window enlarged, Checkpoint/Diff now should manage Layers properly.


3.22: Global Settings now include Scenario Settings (Sinfo.dbf), it lets you change max levels in sagas. GAI.DBF description corrected.
From now on everything is baseline dependant on Dbf Editor for safe work.

3.21: Hotfix: Modifying layers caused issues while loading checkpoints, now its fixed.

3.20: Capital layout will now refresh any time Layers has changed (editing is more comfortable).
There was 1 pixel slippage on grandchild buildings chain, it is fixed.
There was a rare case, where some buildings didnt let other buildings to be built, its now fixed. 
Layout generator fine-tuned.
Adding new buildings now requires an existing baseline.
Asset Browser: Iso.dbi sprites and shadows now can be replaced with different dimension pictures.
Baseline/Reset/Checkpoint fixes

3.19: quality of life changes: right click on building now enable to jump to building editor or unit editor directly,
prev_id, enroll building/upgrade building fields now let you choose from existing ID-s (for easy and clear workflow)

3.18: when more units share the same description, and description are changed now it will only change for 1 unit (create a new description)
instead of changing for all. 
Capital.dbi-s records now can be replaced with different dimension pictures.

3.17: fixed checkpoint/load (some files were not loaded like it intended), fine-tuned evolution generator, and building cost. 

3.16: Now buildings can be positioned with arrow keys and by typing numbers manually,layers can be set manually for more precise work,
right click enables to jump to the building in dbf editor for faster workflow

3.15: fixed various issues in baseline/checkpoint/load function

In 3.14 Building Editor will reuse deleted building records, as the max number of buildings is 99
Minor bugfix: Sideshow buildings are now limited to level 4 not to cause crash.

3.12 now can handle sounds

Building editor now will auto-generate non existing structures to collerate with the new building structure.

New version wont cause crash after replacing images and leaving the tool open.

Now you can decode images with full canvas, checkbox: full canvas

Fixed canvas/bbox diff error while replacing trees/tiles.

Fixed encode/replace, not to generate animated indexes while dithering.

Replace all button, so tiles and trees are now easier to work with.

Wdb files are now extendable

Layout changes to avoid not showing everything in smaller screens.

Grid on spell.ff and iso.ff 

Replace Capital Screens are now possible! Major encoding upgrade and bugfix!

New Tab: Building Editor:

You can add new buildings with this new feature. (Add Linear upgrade for building, or add new Root building)
You can adjust buildings position in Capital Screen Layout.

Baseline/Diff/Load/Reset/Checkpoint now affects every file, not only .dbf files! 
(you can set a baseline, and after that delete/reset/save/load every modification, including graphic and animation and building mods.)

Version 2.1 hotfix: Fixed baseline/diff/load/reset to match the correct files

Fixed dithering while encoding into .ff files! 

Decoding images now will generate 8bit Png files!

Minor bugfixes in encoding.


Known bugs:



*********************************************



With this tool its possible to decode, encode, replace images/animations/sounds in Disciples Sacred Lands. 
(you can use .PNG or .BMP files for images, .GIF files for animations and .WAV files for sound!

With this tool its possible to browse and edit .dbf files for Disciples Sacred Lands!
It can show and generate evolution chains, you can save your mod, you can reset your mod, you can make a diff file to share your mod, you can load your mods with it too!
(Read info first) When you first use .dbf editor you should make a baseline file so you can use delete, reset and see differences. 

With this tool its possible to add new buildings in Disciples Sacred Lands!


https://youtu.be/Tt8QdVC5rUE


https://youtu.be/4wNPHOt-4_E


https://youtu.be/R9qvmONzBSk

<img width="998" height="650" alt="image" src="https://github.com/user-attachments/assets/6ff382fb-2318-4282-822a-1507c23b49b8" />
<img width="998" height="648" alt="image" src="https://github.com/user-attachments/assets/ab50fca0-39c0-4163-a1d8-bc877fa8211d" />
<img width="998" height="655" alt="image" src="https://github.com/user-attachments/assets/8e636462-f5fa-4c5f-9f2a-87707681c591" />
<img width="990" height="650" alt="image" src="https://github.com/user-attachments/assets/670b85e8-77fd-4f8a-a2d6-1818c948cc9a" />
<img width="2556" height="1038" alt="image" src="https://github.com/user-attachments/assets/9844c92a-38d0-484d-afab-2473bddb862b" />
<img width="1231" height="899" alt="image" src="https://github.com/user-attachments/assets/6a1f917f-e18a-40ab-a7e3-7b66a5c13774" />
<img width="454" height="539" alt="image" src="https://github.com/user-attachments/assets/417b05fa-caaf-4aca-b6b0-164089b19d9d" />
<img width="1560" height="853" alt="image" src="https://github.com/user-attachments/assets/87e042d9-504a-448e-a485-e710f6c43b8e" />
<img width="2560" height="1080" alt="image" src="https://github.com/user-attachments/assets/01f5a735-c415-4fc4-8141-03079ff3832f" />
<img width="2560" height="1080" alt="image" src="https://github.com/user-attachments/assets/faf3bb27-1582-401c-847a-7801b53aae0f" />
<img width="2560" height="1080" alt="image" src="https://github.com/user-attachments/assets/0ceea8c3-5c3b-446f-9604-5e0948c129a7" />
<img width="2560" height="1080" alt="image" src="https://github.com/user-attachments/assets/5ce1a8c6-4264-4b55-8852-163d88d2c78c" />
<img width="2560" height="1080" alt="image" src="https://github.com/user-attachments/assets/627ff5d0-096f-4837-bd29-01258bc3f36f" />










