from __future__ import annotations



from knowledge_graph import parse_edge_row, parse_edge_rows, verified_edge_rows, GraphEdge


def test_parse_edge_row():
    """Test parsing a single cross-document edge row."""
    row = {
        "edge_id": "2->1::Van ban huong dan",
        "src_id": " 2 ",
        "dst_id": " 1 ",
        "rel_canonical": "guides_or_details",
        "rel_group": "guidance",
        "rel_raw": "Văn bản hướng dẫn",
        "direction_normalized": "true",
        "direction_verified": "1",
        "external_target": "false",
        "edge_quality_flags": ["some_flag"],
        "provenance": {"rel": "hdsd"}
    }
    
    edge = parse_edge_row(row)
    assert isinstance(edge, GraphEdge)
    assert edge.edge_id == "2->1::Van ban huong dan"
    assert edge.src_id == "2"
    assert edge.dst_id == "1"
    assert edge.rel_canonical == "guides_or_details"
    assert edge.direction_normalized is True
    assert edge.direction_verified is True
    assert edge.external_target is False
    assert edge.edge_quality_flags == ("some_flag",)
    assert edge.provenance == {"rel": "hdsd"}


def test_parse_edge_rows_stream():
    """Test edge stream parsing."""
    rows = [
        {"edge_id": "1->2::1", "src_id": "1", "dst_id": "2", "direction_verified": True},
        {"edge_id": "2->3::2", "src_id": "2", "dst_id": "3", "direction_verified": False}
    ]
    edges = list(parse_edge_rows(rows))
    assert len(edges) == 2
    assert edges[0].edge_id == "1->2::1"
    
    # Filter verified edges
    verified = list(verified_edge_rows(edges))
    assert len(verified) == 1
    assert verified[0].edge_id == "1->2::1"
