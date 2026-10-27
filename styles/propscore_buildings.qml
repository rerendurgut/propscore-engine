<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.34.0" styleCategories="Symbology|Labels">
  <renderer-v2 type="graduatedSymbol" attr="propscore" graduatedMethod="GraduatedColor" forceraster="0" enableorderby="0" symbollevels="0">
    <ranges>
      <range render="true" lower="0.000000000000000" upper="50.000000000000000" symbol="0" label="D (0 - 50) Düşük Erişilebilirlik"/>
      <range render="true" lower="50.000000000000000" upper="65.000000000000000" symbol="1" label="C (50 - 65) Orta Erişilebilirlik"/>
      <range render="true" lower="65.000000000000000" upper="75.000000000000000" symbol="2" label="B (65 - 75) İyi / Dengeli Konum"/>
      <range render="true" lower="75.000000000000000" upper="85.000000000000000" symbol="3" label="A (75 - 85) Yüksek Erişilebilirlik"/>
      <range render="true" lower="85.000000000000000" upper="100.000000000000000" symbol="4" label="A+ (85 - 100) Prime Konum"/>
    </ranges>
    <symbols>
      <symbol type="fill" name="0" alpha="0.85" clip_to_extent="1" force_rhr="0">
        <layer pass="0" class="SimpleFill" locked="0" enabled="1">
          <Option type="Map">
            <Option type="QString" name="color" value="239,68,68,230"/>
            <Option type="QString" name="outline_color" value="153,27,27,255"/>
            <Option type="QString" name="outline_style" value="solid"/>
            <Option type="QString" name="outline_width" value="0.2"/>
          </Option>
        </layer>
      </symbol>
      <symbol type="fill" name="1" alpha="0.85" clip_to_extent="1" force_rhr="0">
        <layer pass="0" class="SimpleFill" locked="0" enabled="1">
          <Option type="Map">
            <Option type="QString" name="color" value="249,115,22,230"/>
            <Option type="QString" name="outline_color" value="154,52,18,255"/>
            <Option type="QString" name="outline_style" value="solid"/>
            <Option type="QString" name="outline_width" value="0.2"/>
          </Option>
        </layer>
      </symbol>
      <symbol type="fill" name="2" alpha="0.85" clip_to_extent="1" force_rhr="0">
        <layer pass="0" class="SimpleFill" locked="0" enabled="1">
          <Option type="Map">
            <Option type="QString" name="color" value="234,179,8,230"/>
            <Option type="QString" name="outline_color" value="133,77,14,255"/>
            <Option type="QString" name="outline_style" value="solid"/>
            <Option type="QString" name="outline_width" value="0.2"/>
          </Option>
        </layer>
      </symbol>
      <symbol type="fill" name="3" alpha="0.85" clip_to_extent="1" force_rhr="0">
        <layer pass="0" class="SimpleFill" locked="0" enabled="1">
          <Option type="Map">
            <Option type="QString" name="color" value="34,197,94,230"/>
            <Option type="QString" name="outline_color" value="22,101,52,255"/>
            <Option type="QString" name="outline_style" value="solid"/>
            <Option type="QString" name="outline_width" value="0.2"/>
          </Option>
        </layer>
      </symbol>
      <symbol type="fill" name="4" alpha="0.9" clip_to_extent="1" force_rhr="0">
        <layer pass="0" class="SimpleFill" locked="0" enabled="1">
          <Option type="Map">
            <Option type="QString" name="color" value="16,185,129,240"/>
            <Option type="QString" name="outline_color" value="6,78,59,255"/>
            <Option type="QString" name="outline_style" value="solid"/>
            <Option type="QString" name="outline_width" value="0.26"/>
          </Option>
        </layer>
      </symbol>
    </symbols>
  </renderer-v2>
</qgis>
