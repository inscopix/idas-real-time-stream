# IDAS Real-time Stream
Inscopix Data Acquisiton System - Real-time Stream

- This python application captures the live video stream from Inscopix 1P Data Acquisition (DAQ) systems and outputs the frames in numpy ndarray format.
- Each individual frame can be fetched by calling the `get_frame` function. This function returns `none` when no new frame is available.

## Flow Chart
  ![rts_workflow](https://github.com/user-attachments/assets/b9cd5842-f5ab-4be8-b75f-6b1df00e6254)

## Stream Parameters

| Stream Parameter  | Data Type     |  Default  | Description |
| ----------------- | ------------- | --------- | ----------- |
| `port`            | unsigned int  |  5014      |  Socket port number to receive the real time stream |
| `Downsample factor`  |  unsigned int  |  2  |  Downsample factor of the incoming real-time stream |
| `file_storage`  |  boolean  |  true  |  Setting this flag enables storage of captured frames automatically |
| `sync_with_recording`  |  boolean  |  true  | Setting this flag enables stream to start only when recording is started through IDAS |


## Supported Platforms

This application requires a specific version of IDAS on Inscopix's Data Acquisition systems.
Please contact Inscopix for more information.
