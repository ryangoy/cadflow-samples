<?php

/*
 * DEPRECATED
 */

define('OAUTH_URL', 'https://cadflow.auth0.com/oauth/token');
define('API_URL', 'https://api2.cadflow.ai');
define('UPLOAD_ENDPOINT', API_URL . '/upload-file');
define('POLL_ENDPOINT', API_URL . '/poll-file/');
define('POLL_INTERVAL', 15);

class CADflow
{
  private $client_id = null;
  private $refresh_token = null;
  private $access_token = null;
  private $file_id = null;
  private $verbose = false;

  /**
   * @param	string	$client_id		Client ID provided by CADflow.
   * @param	string	$refresh_token	Client secret provided by CADflow.
   */
  public function __construct($client_id, $refresh_token)
  {
    if (empty($client_id) || empty($refresh_token)) {
      throw new Exception('ID and token must be passed to the constructor.');
    }

    $this->client_id = $client_id;
    $this->refresh_token = $refresh_token;
  }

  /**
   * Be verbose.
   *
   * @param	bool	$bool	True is yes, false is no. Default is no.
   */
  public function set_verbose($bool)
  {
    $this->verbose = $bool;
  }

  /**
   * Get an access token from CADflow. This stores the token
   * in $this->access_token.
   *
   * @return	bool	On success.
   */
  public function get_token()
  {
    $data = array(
      'grant_type' => 'refresh_token',
      'client_id' => $this->client_id,
      'refresh_token' => $this->refresh_token,
      'audience' => 'https://cadflow.ai/api'
    );

    $ch = curl_init(OAUTH_URL);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_HTTPHEADER, array(
      'Content-Type: application/x-www-form-urlencoded'
    ));
    curl_setopt($ch, CURLOPT_POSTFIELDS, http_build_query($data));

    if ($this->verbose === true) { curl_setopt($ch, CURLOPT_VERBOSE, true); }

    $json = json_decode(curl_exec($ch));

    if ($json === false) {
      throw new Exception('No response or bad response.');
    }

    if (isset($json->error)) {
      throw new Exception('Error: ' . $json->error . '; '
                          . $json->error_description);
    }

    $this->access_token = $json->access_token;

    return true;
  }

  /**
   * Send an STL file with brackets to have the brackets removed. Save
   * the work ID in $this->file_id to identify job.
   *
   * @param	string	$file		Full path to the file.
   * @param	string	$practice_id	Our ID for the practice.
   * @param	string	$prescription_id	Our ID for the case.
   * @param	bool	$abr	Remove brackets?
   * @param	bool	$base	Add a base?
   * @param	bool	$trim	Trim the model?
   *
   * @return	bool	On success.
   */
  public function process_file($file, $practice_id = 0,
                               $prescription_id = 0,
                               $abr = true, $base = false, $trim = false)
  {
    if (!$this->access_token) {
      throw new Exception('No access token.');
    }

    $data = array(
      'filename' => basename($file),
      'practice_id' => $practice_id,
      'prescription_id' => $prescription_id,
      'prescription' => array(
        'abr' => $abr,
        'basing' => $base,
        'trim' => $trim,
      ),
    );

    $ch = curl_init(UPLOAD_ENDPOINT);
    curl_setopt($ch, CURLOPT_CUSTOMREQUEST, 'PUT');
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_HTTPHEADER, array(
      'Content-Type: application/json',
      'Authorization: Bearer ' . $this->access_token
    ));
    curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($data));

    if ($this->verbose === true) { curl_setopt($ch, CURLOPT_VERBOSE, true); }

    $json = json_decode(curl_exec($ch));
    $c = curl_getInfo($ch, CURLINFO_HTTP_CODE);

    if ($json === false) {
      throw new Exception('No response or bad response while uploading.');
    }

    if ($c != 200) {
      if ($json->message) {
        throw new Exception($json->message);
      } else {
        throw new Exception('Unknown error scheduling file upload.');
      }
    }

    $this->upload_url = $json->url;
    $this->file_id = $json->fid;

    $fh = fopen($file, 'rb');
    $size = filesize($file);

    if (!$fh) {
      throw new Exception('Could not open file for reading.');
    }

    $ch = curl_init($this->upload_url);
    curl_setopt($ch, CURLOPT_PUT, true);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_BINARYTRANSFER, true);
    curl_setopt($ch, CURLOPT_HTTPHEADER, array(
      'Content-Type: model/stl',
      'Content-Length: ' . $size,
    ));

    curl_setopt($ch, CURLOPT_INFILE, $fh);
    curl_setopt($ch, CURLOPT_INFILESIZE, $size);

    if ($this->verbose === true) { curl_setopt($ch, CURLOPT_VERBOSE, true); }

    curl_exec($ch);
    $c = curl_getInfo($ch, CURLINFO_HTTP_CODE);

    if ($c != 200) {
      throw new Exception('Unable to put file.');
    }

    return true;
  }

  /**
   * Set the file_id received by a previous call to process_file() so
   * that it can be polled for and downloaded.
   *
   * @param	int	$id	File ID from prior call to process_file().
   *
   * @return	void
   */
  public function set_file_id($id)
  {
    $this->file_id = $id;
  }

  /**
   * Get the file_id received by a previous call to process_file() so
   * that it can be saved for later poll and download.
   *
   * @return	int	File ID from call to process_file().
   */
  public function get_file_id()
  {
    return $this->file_id;
  }

  /**
   * Poll CADflow for processed file and download it. Polling is done
   * using the $this->file_id to identify work.
   *
   * @param	string	$file	The file to save to.
   * @param	int	$attempt	How many times to poll for the file.
   *
   * @throws	Exception	On failure to communicate with server.
   * @throws	Exception	On failure to retrieve processed file.
   *
   * @return	bool, int	False if file not ready, else bytes read.
   */
  public function poll_and_download($file, $attempt = 10)
  {
    if ($this->file_id === null) {
      throw new Exception('No file_id, call process_file() or set_file_id().');
    }

    for ($i = 0; $i < $attempt; $i++) {

      $ch = curl_init(POLL_ENDPOINT . $this->file_id);
      curl_setopt($ch, CURLOPT_POST, true);
      curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
      curl_setopt($ch, CURLOPT_HTTPHEADER, array(
        'Authorization: Bearer ' . $this->access_token
      ));

      if ($this->verbose === true) { curl_setopt($ch, CURLOPT_VERBOSE, true); }

      $json = json_decode(curl_exec($ch));
      $c = curl_getInfo($ch, CURLINFO_HTTP_CODE);

      if ($json === false) {
        throw new Exception('No response or bad response while polling.');
      }

      if ($c == 200) {
        $data = file_get_contents($json->url);

        $fp = fopen ($file, 'w+');

        if (!$fp) {
          throw new Exception('Unable to open file for saving.');
        }

        $ch = curl_init($json->url);
        curl_setopt($ch, CURLOPT_FILE, $fp);
        curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);
        if ($this->verbose === true) {
          curl_setopt($ch, CURLOPT_VERBOSE, true);
        }
        curl_exec($ch);
        $c = curl_getInfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);
        fclose($fp);

        $bytes = filesize($file);
        if ($bytes === 0 || $c !== 200) {
          throw new Exception('Unable to retrieve processed file.');
        }

        return $bytes;

      } else if ($c == 400) {
        if ($json->message) {
          throw new Exception('400: ' . $json->message);
        } else {
          throw new Exception('Error code 400 while polling.');
        }
      } else if ($c == 503) {
        if ($json->message) {
          throw new Exception('503: ' . $json->message);
        } else {
          throw new Exception('Error code 503 while polling.');
        }
      } else {
        sleep(POLL_INTERVAL);
      }
    }

    return false;
  }
}

