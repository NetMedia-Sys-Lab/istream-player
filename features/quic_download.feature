Feature: The player should be able to download files using QUIC (HTTP/3)
  Scenario: The QUIC client could download files
    Given A QUIC Client
    When The client is asked to get content from an URL
    Then The client get it