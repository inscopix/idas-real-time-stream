import cv2
import numpy as np
import time

class isx_scope(object):

    def __init__(self, port=5014, downsample_factor=2, file_storage=False, sync_with_recording=False):
        '''
        Initializes Inscopix real time stream application

        :param port: port number of the real time stream
        :param downsample_factor: down sample factor set on Inscopix hub
        :param file_storage: set flag to true to enable storage of raw video.
                             File name will be isx_stream_<timestamp>.raw
        :param sync_with_recording: set flag to true to enable sync with isxd record
                            Frames will be streamed and recorded in this app,
                            only when recording is started on the Inscopix FE.
        '''

        print ('Initializing Inscopix Real time stream')
        print ('Creating Real time stream on Port: %d, with downsample factor: %d' % (port, downsample_factor))
        self.isx_set_defaults(downsample_factor)

        self.sync_with_recording = sync_with_recording
        if sync_with_recording:
            print ('Sync with recording enabled')
            print ('Start recording on Inscopix Frontend to view the stream')
        else:
            print ('Sync with recording disabled')

        self.file_storage = file_storage
        if self.file_storage:
            self.file_to_write = 'isx_stream_' + str(int(time.time())) + '.raw'
            self.file_pointer = open(self.file_to_write, 'wb')
            print ('File storage enabled. storage file:', self.file_to_write)
        else:
            print ('File storage disabled.')

        self.isx_stream_port = port
        self.video_source = 'udpsrc port={}'.format(self.isx_stream_port)

        self.caps_application_pre = "application/x-rtp, media=(string)video"
        self.caps_application_post = ", encoding-name=(string)RAW, " \
                          "sampling=(string)RGBA, depth=(string)8"

        self.buffer_string = " buffer-size=" + str(self.frame_size_in_bytes)
        self.video_caps = " caps=\"" + self.caps_application_pre + \
                         ", width=(string)" + str(self.stream_width) + \
                         ", height=(string)" + str(self.stream_height) + \
                          self.caps_application_post + "\""

        self.video_container = " ! rtpvrawdepay"
        self.video_parser = " ! queue ! rawvideoparse format=gray8 " + \
                            "frame-size=" + str(self.frame_size_in_bytes) + \
                            " width=" + str(self.frame_width) + \
                            " height=" + str(self.frame_height) + \
                            " disable-passthrough=false"

        self.video_sink = " ! appsink"

        self.video_pipeline = self.video_source + self.buffer_string + \
                             self.video_caps + self.video_container + \
                             self.video_parser + self.video_sink

        self.frame_statistics = {'missing_frames_range': [], 'seq_id': 0, 'isxd_record': False}

    def isx_set_defaults(self, ds_factor):
        '''
        sets the default values for Inscopix streaming.
        *Do not modify the constants*

        :param ds_factor: downsample factor of the incoming video stream
        :return: none
        '''

        #Default dimensions of isx microscope
        isx_default_width = 1280
        isx_default_height = 800
        isx_meta_header_length = 2
        isx_meta_footer_length = 2
        isx_meta_fc_offset = 1258
        isx_meta_ad_flag_offset = 1257
        size16 = 2
        size32 = 4

        isx_meta_header_bytes = isx_meta_header_length * isx_default_width * size16
        isx_meta_footer_bytes = isx_meta_footer_length * isx_default_width * size16

        isx_meta_total_bytes = isx_meta_header_bytes + isx_meta_footer_bytes

        #We pack the incoming stream into 32bit format containing
        #two 16bit values per pixel. So, stream dimensions has to be adjusted
        self.stream_width = isx_default_width // ds_factor
        stream_height = isx_default_height // ds_factor
        header_footer_line_count_16bit = (isx_meta_total_bytes // self.stream_width)
        header_footer_line_count_32bit = (header_footer_line_count_16bit * size16)// size32
        self.stream_height = stream_height + header_footer_line_count_32bit

        #converting 32-bit to 8-bit pixels for appsink compatibility
        self.frame_width = self.stream_width * (size32 // size16)
        self.frame_height = self.stream_height * (size32 // size16)

        self.frame_size_in_bytes = self.frame_width * self.frame_height

        self.isx_header_offset = isx_meta_header_bytes // (size16 * self.stream_width)
        self.isx_footer_offset = stream_height + self.isx_header_offset

        self.header_row_with_meta = isx_meta_fc_offset // self.stream_width
        self.frame_counter_offset = isx_meta_fc_offset - (self.header_row_with_meta * self.stream_width)
        self.frame_record_flag_offset = isx_meta_ad_flag_offset - (self.header_row_with_meta * self.stream_width)

        self.frame_record_flag_value = 0xAD0
        self.prev_frame_seq_id = 0

        print ("Use Frame dimensions: width: %d, Height: %d" % (self.stream_width, stream_height))

    def start_stream(self):
        '''
        Opens a video capture pipeline through gstreamer.
        video pipeline is configured to stream raw calcium data
        :return: True on successful opening of video capture pipeline
                 False otherwise
        '''

        try:

            self.stream_capture = cv2.VideoCapture(self.video_pipeline, cv2.CAP_GSTREAMER)

            if not self.stream_capture.isOpened():
                print ('Isx stream video capture is not opened')
                return False

            print ('Isx stream video capture is started')
            return True

        except Exception as e:

            print ('Unhandled exception while starting isx stream: %s' % e)
            return False

    def stop_stream(self):
        '''
        Stops the video capture pipeline
        :return: True on success, False otherwise
        '''

        try:

            self.stream_capture.release()
            print ('Stream video capture is stopped')
            if self.file_storage:
                self.file_pointer.close()
            return True

        except Exception as e:

            print ('Unhandled exception while stopping isx stream: %s' % e)
            return False

    def get_frame(self):
        '''
        reads the latest frame from the video capture pipeline
        Stores the frame into file if file storage is enabled
        :return:    On unsuccessful read - None
                    On successful read -
                    frame_statistics - JSON containing sequence id of the frame
                                       and missing sequence ids since last successful read
                    frame - frame data packed in 16bit format
        '''

        try:

            ret, raw = self.stream_capture.read()

            if not ret:

                print ('Stream captured empty frame')
                return None, None

            #Change the 8-bit raw frame to 16-bit format
            frame16 = raw.view(dtype=np.uint16)

            #strip off the header and footer offset from the 16-bit frame
            frame = frame16[self.isx_header_offset: self.isx_footer_offset]

            isxd_record_status = self.update_frame_stats(frame16[self.header_row_with_meta])

            if self.sync_with_recording and not isxd_record_status:
                return None, None

            if self.file_storage:
                self.file_pointer.write(frame)

            return (self.frame_statistics, frame)

        except Exception as e:

            print ('Exception while getting frame: %s' % e)
            return None, None


    def update_frame_stats(self, frame_header_row):
        '''
        Updates the frame statistics such as frame sequence id and
        range of missing frame sequence ids
        :param frame_header_row: Header row containing the frame metadata
        :return: None
        '''

        try:

            curr_frame_seq_id = \
                    (((frame_header_row [self.frame_counter_offset] >> 4) << 0) | \
                    ((frame_header_row [self.frame_counter_offset + 1] >> 4) << 8) | \
                    ((frame_header_row [self.frame_counter_offset + 2] >> 4) << 16) | \
                    ((frame_header_row [self.frame_counter_offset + 3] >> 4) << 24))

            frame_record_byte = frame_header_row[self.frame_record_flag_offset]
            if frame_record_byte == self.frame_record_flag_value:
                curr_frame_is_recording = True
            else:
                curr_frame_is_recording = False

            self.frame_statistics = {'missing_frames_range': [], 'seq_id': curr_frame_seq_id, 'isxd_record': curr_frame_is_recording}

            if self.prev_frame_seq_id != 0 \
                    and curr_frame_seq_id != self.prev_frame_seq_id + 1:

                # If current seq id is not the next expected, then report range of missing seq ids
                self.frame_statistics['missing_frames_range'] = [self.prev_frame_seq_id+1, curr_frame_seq_id-1]

            self.prev_frame_seq_id = curr_frame_seq_id

            return curr_frame_is_recording

        except Exception as e:

            print ('Unhandled exception while getting frame stats: %s' % e)
            return False


def run_example_app():
    '''
    Example application to demonstrate the working of
    Inscopix real time calcium stream access

    :return: None
    '''

    try:
        scope = isx_scope(port=5014, downsample_factor=2, file_storage=True, sync_with_recording=True)
        scope.start_stream()

        while True:

            stats, frame = scope.get_frame()

            if stats:
                print('Got Frame #', stats['seq_id'], \
                      ' Isxd record flag', stats['isxd_record'], \
                      ' Missing frames: ', str(stats['missing_frames_range']))

    except (KeyboardInterrupt, SystemExit):

        print ('Kill received. Exiting cleanly')
        scope.stop_stream()
        return

if __name__ == "__main__":

    run_example_app()