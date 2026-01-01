def test_widget(make_napari_viewer):
    from napari_padbound import PadboundWidget

    viewer = make_napari_viewer()
    widget = PadboundWidget(viewer)

    assert widget is not None
