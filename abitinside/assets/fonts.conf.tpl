<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">
<!-- A Bit Inside: the video uses exactly four font files, loaded by path.
     Nothing is ever resolved from a system font directory. -->
<fontconfig>
  <dir prefix="default">FONTS_DIR</dir>
  <cachedir prefix="default">CACHE_DIR</cachedir>

  <alias binding="strong">
    <family>Poppins</family>
    <prefer><family>Poppins</family></prefer>
  </alias>
  <alias binding="strong">
    <family>JetBrains Mono</family>
    <prefer><family>JetBrains Mono</family></prefer>
  </alias>

  <match target="pattern">
    <test name="family" compare="eq"><string>ABit Bold</string></test>
    <edit name="file" mode="assign" binding="strong"><string>FONT_POPPINSBOLD</string></edit>
  </match>
  <match target="pattern">
    <test name="family" compare="eq"><string>ABit SemiBold</string></test>
    <edit name="file" mode="assign" binding="strong"><string>FONT_POPPINSSEMIBOLD</string></edit>
  </match>
  <match target="pattern">
    <test name="family" compare="eq"><string>ABit Regular</string></test>
    <edit name="file" mode="assign" binding="strong"><string>FONT_POPPINSNORMAL</string></edit>
  </match>
  <match target="pattern">
    <test name="family" compare="eq"><string>ABit Mono</string></test>
    <edit name="file" mode="assign" binding="strong"><string>FONT_JBMONO</string></edit>
  </match>

  <!-- map cairo's synthetic weight/oblique requests onto the real files -->
  <match target="pattern">
    <test qual="any" name="family"><string>Poppins</string></test>
    <test name="weight" compare="eq"><const>bold</const></test>
    <edit name="file" mode="assign" binding="same"><string>FONT_POPPINSBOLD</string></edit>
  </match>
  <match target="pattern">
    <test qual="any" name="family"><string>Poppins</string></test>
    <test name="weight" compare="eq"><const>medium</const></test>
    <edit name="file" mode="assign" binding="same"><string>FONT_POPPINSSEMIBOLD</string></edit>
  </match>
  <match target="pattern">
    <test qual="any" name="family"><string>Poppins</string></test>
    <edit name="file" mode="assign" binding="same"><string>FONT_POPPINSBOLD</string></edit>
  </match>
  <match target="pattern">
    <test qual="any" name="family"><string>JetBrains Mono</string></test>
    <edit name="file" mode="assign" binding="same"><string>FONT_JBMONO</string></edit>
  </match>
</fontconfig>